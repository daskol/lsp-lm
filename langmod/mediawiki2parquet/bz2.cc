#include "bz2.h"

#include <cstdlib>

namespace mediawiki {

ibz2streambuf::ibz2streambuf(std::istream &is) noexcept
    : is_{is}
    , get_buf_{std::make_unique<char_type[]>(kBufSize)}
    , src_buf_{std::make_unique<char_type[]>(kBufSize)}
{
    auto *begin = get_buf_.get();
    auto *end = begin + kBufSize;
    setg(begin, end, end);
}

std::streamsize ibz2streambuf::showmanyc(void) {
    if (gptr() < egptr()) {
        return static_cast<std::streamsize>(egptr() - gptr());
    } else {
        return 0;
    }
}

int ibz2streambuf::underflow(void) {
    if (!is_.good()) {
        return traits_type::eof();
    }

    // If get buffer is not empty then return the current char.
    if (gptr() < egptr()) {
        return *gptr();
    }

    auto *begin = eback();
    auto length = static_cast<size_t>(gptr() - eback());
    auto read = read_chunk(begin, length);

    if (read) {
        setg(begin, begin, begin + *read);
        return *gptr();
    } else {
        setg(begin, begin, begin);
        return traits_type::eof();
    }
}

std::streamsize ibz2streambuf::xsgetn(char_type *ptr, std::streamsize size) {
    std::streamsize rest = size;

    // Copy buffered content as much as possible to the provided buffer.
    if (gptr() < egptr()) {
        std::streamsize avail = static_cast<std::streamsize>(egptr() - gptr());
        std::streamsize length = std::min(avail, size);
        std::copy(gptr(), gptr() + length, ptr);
        // Advance pointer to rest of buffer and adjust length of an empty part
        // of buffer.
        ptr += length;
        rest -= length;
        // Adjust state of the stream buffer.
        setg(eback(), gptr() + length, egptr());
    }

    // Read as much as possible from a source stream directly to the provided
    // buffer until buffer is full.
    do {
        if (auto read = read_chunk(ptr, rest); !read) {
            break;
        } else {
            ptr += *read;
            rest -= *read;
        }
    } while (rest > 0);

    return size - rest;
}

std::optional<size_t> ibz2streambuf::read_chunk(char_type *ptr, size_t size) {
    switch (state_) {
    case State::Init:
        if (auto err = BZ2_bzDecompressInit(&bs_, 0, 0); err != BZ_OK) {
            BZ2_bzDecompressEnd(&bs_);
            state_ = State::Term;
            return std::nullopt;
        } else {
            state_ = State::Main;
            return inflate_chunk(ptr, size);
        }
    case State::Main:
        return inflate_chunk(ptr, size);
    case State::Term:
        return std::nullopt;
    default:
        std::abort(); // Unreachable.
    }
}

std::optional<size_t> ibz2streambuf::inflate_chunk(char_type *ptr, size_t size) {
    do {
        if (bs_.avail_in < kBufSize && is_.good()) {
            std::move(bs_.next_in, bs_.next_in + bs_.avail_in, src_buf_.get());
            is_.read(src_buf_.get() + bs_.avail_in, kBufSize - bs_.avail_in);
            bs_.avail_in += is_.gcount();
            bs_.next_in = reinterpret_cast<char *>(src_buf_.get());
        }

        // Set up output buffer which points to the get buffer.
        bs_.avail_out = size;
        bs_.next_out = reinterpret_cast<char *>(ptr);

        switch (auto err = BZ2_bzDecompress(&bs_); err) {
        case BZ_OK:
            if (auto diff = size - bs_.avail_out; diff > 0) {
                return diff;
            } else if (!is_.eof()) {
                break;
            } else {
                [[fallthrough]];
            }
        case BZ_STREAM_END:
            BZ2_bzDecompressEnd(&bs_);
            state_ = State::Term;
            if (auto diff = size - bs_.avail_out; diff > 0) {
                return diff;
            } else {
                return std::nullopt;
            }
        case BZ_PARAM_ERROR:
        case BZ_DATA_ERROR:
        case BZ_DATA_ERROR_MAGIC:
        case BZ_MEM_ERROR:
            BZ2_bzDecompressEnd(&bs_);
            state_ = State::Term;
            return std::nullopt;
        }
    } while (true);
}

} // namespace NNoesis

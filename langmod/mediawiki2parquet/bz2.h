#pragma once

#include <iostream>
#include <memory>
#include <optional>

#include <bzlib.h>

namespace mediawiki {

class ibz2streambuf : public std::streambuf {
private:
    enum class State : uint8_t {
        Init,
        Main,
        Term,
    };

public:
    static constexpr size_t kBufSize = 16384;

public:
    ibz2streambuf(void) = delete;

    ibz2streambuf(std::istream &is) noexcept;

    virtual ~ibz2streambuf(void) = default;

protected:
    virtual std::streamsize showmanyc(void) override;

    virtual int underflow(void) override;

    virtual std::streamsize xsgetn(char_type *ptr, std::streamsize size) override;

private:
    std::optional<size_t> read_chunk(char_type *ptr, size_t size);

    std::optional<size_t> inflate_chunk(char_type *ptr, size_t size);

private:
    std::istream &is_;
    std::unique_ptr<char_type[]> get_buf_; // Get buffer.
    std::unique_ptr<char_type[]> src_buf_; // Source buffer.

    ::bz_stream bs_ = {
        .next_in = nullptr,
        .avail_in = 0,
        .total_in_lo32 = 0,
        .total_in_hi32 = 0,

        .next_out = nullptr,
        .avail_out = 0,
        .total_out_lo32 = 0,
        .total_out_hi32 = 0,

        .state = nullptr,

        .bzalloc = nullptr,
        .bzfree = nullptr,
        .opaque = nullptr,
    };

    State state_ = State::Init;
};

} // namespace mediawiki

/**
 * \file main.cc
 */

#include <filesystem>
#include <iostream>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include <langmod/mediawiki/util.h>
#include <langmod/mediawiki2parquet/transform.h>

namespace {

namespace fs = std::filesystem;
namespace mw = mediawiki;

using std::literals::string_view_literals::operator""sv;

constexpr std::string_view usage = R"(
Usage: mw convert [OPTIONS] <SRC> <DST>

Arguments
  <SRC>     Either Wikipedia dump or directory with dumps.
  <DST>     Either name of output file or directory to store processed dumps.

Options
  --compression-codec <zstd>    Compression codec for output files.
  --compression-level <uint>    Compression level for output files.
  --filetype <bzip2|xml>        How to interpret source files.
  --help                        Show this message.
  --threads                     Number of threads.
)"sv.substr(1);

struct Options {
    bool usage = false;

    std::string src;
    std::string dst;

    std::string compression_codec;
    uint64_t compression_level = 0;
    mw::FileType filetype = mw::FileType::Unknown;
    uint64_t nothreads = 0;
};

class OptParsingError : public std::runtime_error {
public:
    OptParsingError(std::string const &what_arg)
        : std::runtime_error(what_arg)
    {}

    OptParsingError(char const *what_arg)
        : std::runtime_error(what_arg)
    {}

    OptParsingError(OptParsingError const &other) noexcept = default;
};

Options ParseOptions(std::vector<std::string> const &args) {
    Options opts;
    std::vector<std::string> positional;

    OptParsingError exc_few_options("too few options");
    OptParsingError exc_parse_error("failed to parse option value");
    OptParsingError exc_missing_command("missing CLI command");
    OptParsingError exc_unknown_command("unknown CLI command");

    if (args.size() < 2) {
        throw exc_missing_command;
    }

    if (args[1] != "convert") {
        throw exc_unknown_command;
    }

    auto beg = args.begin();
    auto end = args.end();
    auto it = beg + 2;
    for (; it != end; ++it) {
        if (*it == "--help") {
            opts.usage = true;
            break;
        } else if (*it == "--compression-codec") {
            if (++it == end) {
                throw exc_few_options;
            } else {
                opts.compression_codec = *it;
            }
        } else if (*it == "--compression-level") {
            if (++it == end) {
                throw exc_few_options;
            } else if (auto val = mw::ParseUInt64(*it); !val) {
                throw exc_parse_error;
            } else {
                opts.compression_level = *val;
            }
        } else if (*it == "--filetype") {
            if (++it == end) {
                throw exc_few_options;
            } else if (auto val = mw::ParseFileType(*it); !val) {
                throw exc_parse_error;
            } else {
                opts.filetype = *val;
            }
        } else if (*it == "--threads") {
            if (++it == end) {
                throw exc_few_options;
            } else if (auto val = mw::ParseUInt64(*it); !val) {
                throw exc_parse_error;
            } else {
                opts.nothreads = *val;
            }
        } else {
            positional.emplace_back(std::move(*it));
        }
    }

    if (positional.size() != 2) {
        throw OptParsingError("too few positional arguments");
    }

    opts.src = positional[0];
    opts.dst = positional[1];

    return opts;
}

std::vector<fs::path> GatherSourceFiles(fs::path const &path) {
    std::error_code ec;
    fs::directory_iterator dir(path, ec);
    if (ec) {
        std::cerr << "ERR error occur: \n"; // TODO: ...
        return {};
    }

    std::vector<fs::path> srcs;
    for (auto const &entry : dir) {
        if (!entry.is_regular_file(ec)) {
            std::cout << "not a file\n";
            return {};
        } else if (ec) {
            std::cout << "failed to stat file\n";
            return {};
        }

        srcs.emplace_back(std::move(entry.path()));
    }

    return srcs;
}

std::vector<fs::path> MakeTargetFiles(fs::path const &dst, std::vector<fs::path> const &srcs) {
    fs::path const bz2 = ".bz2", bzip2 = ".bzip2", parquet = ".parquet";

    std::unordered_map<std::string, size_t> dups; // Store duplicates.
    std::vector<fs::path> dsts;
    dsts.reserve(srcs.size());

    for (auto const &src : srcs) {
        fs::path filename = src.filename();
        if (auto ext = filename.extension(); ext == bz2 || ext == bzip2) {
            filename = filename.stem();
        }

        size_t count;
        if (auto [it, ok] =  dups.insert({filename.stem().string(), 0}); ok) {
            count = 0;
        } else {
            count = ++it->second;
        }

        fs::path part = ".part-" + std::to_string(count);
        filename = filename.stem();
        filename += part;
        filename += parquet;
        dsts.emplace_back(dst / filename);
    }

    return dsts;
}

int Run(std::vector<std::string> const &args) {
    Options opts;

    try {
        opts = ParseOptions(args);
    } catch (OptParsingError const &exc) {
        std::cout << "ERR failed to parse argument options: "
                  << exc.what() << '\n';
        std::cout << usage;
        return 1;
    }

    if (opts.usage) {
        std::cout << usage;
        return 0;
    }

    std::vector<fs::path> srcs, dsts;
    try {
        // Preprocess <src> argument first.
        if (!fs::exists(opts.src)) {
            std::cerr << "ERR there is no such path: " << opts.src << '\n';
            return 1;
        }

        fs::path src = fs::canonical(opts.src);

        switch (fs::status(src).type()) {
        case fs::file_type::directory:
            srcs = GatherSourceFiles(src);
            break;
        case fs::file_type::regular:
            srcs.push_back(src);
            break;
        default:
            break;
        }

        if (srcs.empty()) {
            std::cerr << "ERR failed to gather list of source files\n";
            return 1;
        }

        // Now we can preprocess <dst> argument.
        fs::path dst(opts.dst);
        if (dst.is_relative()) {
            dst = fs::current_path() / dst;
        }
        dst = dst.lexically_normal();

        if (srcs.size() == 1) {
            dsts.push_back(dst);
            dst = dst.parent_path();
        } else {
            dsts = MakeTargetFiles(dst, srcs);
        }

        std::error_code ec;
        fs::create_directories(dst, ec);
        if (ec) {
            std::cerr << "ERR failed to create output directory " << dst
                      << ": " << ec.message() << '\n';
            return 1;
        }

        // Sanity check.
        if (srcs.size() != dsts.size()) {
            std::cerr << "ERR wrong numbers of source and target files\n";
            return 1;
        }
    } catch (std::filesystem::filesystem_error const &exc) {
        std::cout << "ERR " << exc.what() << '\n';
        return 1;
    }

    std::cout << "INF total " << srcs.size() << " partition(s)\n";
    mw::Transform(srcs, dsts, opts.nothreads);
    return 0;
}

} // namespace

int main(int argc, char *argv[]) {
    return Run({argv, argv + argc});
}

#include "transform.h"

#include <array>
#include <thread>

#include <langmod/mediawiki/util.h>
#include <langmod/mediawiki/wiki.h>
#include <langmod/mediawiki2parquet/bz2.h>
#include <langmod/mediawiki2parquet/queue.h>
#include <langmod/mediawiki2parquet/writer.h>

namespace mediawiki {

std::istream &operator>>(std::istream &is, FileType &ft) {
    std::string str;
    is >> str;
    if (auto res = ParseFileType(str); res) {
        ft = *res;
    } else {
        ft = FileType::Unknown;
    }
    return is;
}

std::ostream &operator<<(std::ostream &os, FileType ft) {
    switch (ft) {
    default:
        [[fallthrough]];
    case FileType::Unknown:
        return os << "Unknown";
    case FileType::BZip2:
        return os << "BZip2";
    case FileType::XML:
        return os << "XML";
    }
}

std::optional<FileType> ParseFileType(std::string_view view) {
    if (view == "bzip2") {
        return FileType::BZip2;
    } else if (view == "xml") {
        return FileType::XML;
    } else {
        return std::nullopt;
    }
}

FileType GuessFileType(std::ifstream &ifs) {
    auto pos = ifs.tellg();
    auto ft = GuessFileType(static_cast<std::istream &>(ifs));
    ifs.seekg(pos);
    return ft;
}

FileType GuessFileType(std::istream &is) {
    // Read signature bytes.
    std::array<char, 4> buf = {};
    if (!is.get(buf.data(), buf.size())) {
        return FileType::Unknown;
    }

    // Check if file type is bzip2.
    if (std::string_view(buf.data(), 3u) == "BZh") {
        return FileType::BZip2;
    }

    // Otherwise, assume that filetype is XML.
    return FileType::XML;
}

FileType GuessFileType(std::string const &filename) {
    std::ifstream ifs(filename, std::ios::binary);
    if (!ifs) {
        return FileType::Unknown;
    }
    return GuessFileType(ifs);
}

using TransformJob = std::tuple<fs::path, fs::path>;

size_t Transform(std::istream &is, std::string const &dst) {
    auto writer = PageWriter::Create(dst);
    PageReader reader(is);
    size_t count = 0;
    while (reader.Next()) {
        auto page = reader.Read();
        writer->Write(page);
        ++count;
    }
    return count;
}

/**
 * Function Transform reads XML dump, extract pages and store them to Parquet
 * file.
 */
size_t Transform(std::string const &src, std::string const &dst) {
    std::ifstream ifs(src);
    if (!ifs) {
        std::cerr << "ERR failed to open file: " << src << '\n';
        return 0;
    }

    if (auto ft = GuessFileType(ifs); ft == FileType::Unknown) {
        std::cout << "ERR failed to detect file type\n";
        return 0;
    } else if (ft == FileType::BZip2) {
        ibz2streambuf ibz2buf(ifs);
        std::istream is(&ibz2buf);
        return Transform(is, dst);
    } else if (ft == FileType::XML) {
        return Transform(ifs, dst);
    } else {
        std::cout << "ERR unknown file type\n";
        return 0;
    }
}

void Transform(Queue<TransformJob> &queue, size_t index = 0) {
    std::stringstream ss;
    ss.str("");
    ss << "[" << index << "] worker started\n";
    std::cout << ss.str();

    std::optional<TransformJob> job;
    while ((job = queue.Dequeue())) {
        ss.str("");
        ss << "[" << index << "] processing " << std::get<0>(*job).filename() << '\n';
        std::cout << ss.str();

        auto src = std::get<0>(*job).string();
        auto dst = std::get<1>(*job).string();
        size_t count = Transform(src, dst);

        ss.str("");
        ss << "[" << index << "] " << count << " records processed\n";
        std::cout << ss.str();
    }

    ss.str("");
    ss << "[" << index << "] worker exited\n";
    std::cout << ss.str();
}

size_t Transform(std::vector<fs::path> const &srcs, std::vector<fs::path> const &dsts, size_t nothreads) {
    if (srcs.size() != dsts.size()) {
        std::clog << "wrong numbers of sources and targets\n";
        return 0; // TODO: Handle error in any way.
    }

    if (srcs.empty()) {
        std::clog << "nothing to do\n";
        return 0;
    }

    // Initialize job queue.
    size_t nojobs = srcs.size();
    std::vector<TransformJob> jobs;
    jobs.reserve(nojobs);
    for (size_t it = 0; it != nojobs; ++it) {
        jobs.push_back({srcs[it], dsts[it]});
    }
    Queue<TransformJob> queue(jobs, true);

    // Set up a number of threads to spawn if it is not specified.
    if (nothreads == 0) {
        nothreads = std::thread::hardware_concurrency();
    }

    // Adjust number of threads. There is no reason to start threads more than
    // a number of jobs.
    if (nothreads > nojobs) {
        nothreads = nojobs;
    }

    // Spawn threads and run workers.
    std::vector<std::thread> pool;
    pool.reserve(nothreads - 1);
    for (size_t it = 1; it != nothreads; ++it) {
        pool.emplace_back([index=it, &queue] (void) {
            Transform(queue, index);
        });
    }

    // Run one worker in the current thread.
    Transform(queue);

    // Wait while workers finish.
    for (auto &thread : pool) {
        thread.join();
    }

    return 0;
}

} // namespace mediawiki

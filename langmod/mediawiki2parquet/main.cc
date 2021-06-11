/**
 * \file main.cc
 */

#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include <langmod/mediawiki/wiki.h>
#include <langmod/mediawiki2parquet/writer.h>

namespace {

namespace mw = mediawiki;

/**
 * Function transform reads XML dump, extract pages and store them to Parquet
 * file.
 */
void transform(std::string const &src, std::string const &dst) {
    std::ifstream ifs(src);
    if (!ifs) {
        std::cerr << "failed to open file: " << src << '\n';
        return;
    }

    auto writer = mw::PageWriter::Create(dst);
    mw::PageReader reader(ifs);
    size_t count = 0;
    while (reader.Next()) {
//        if (count == 20) {
//            break;
//        }

        auto page = reader.Read();
        writer->Write(page);

        if (++count % 1000 == 0) {
            std::cout << count << " record(s) processed\n";
        }
    }

    std::cout << "total " << count << " records were processed\n";
}

int run(std::vector<std::string> const &args) {
    if (args.size() != 3) {
        std::clog << "usage: " << args[0] << " <src> <dst>\n";
        return 1;
    }

    transform(args[1], args[2]);
    return 0;
}

} // namespace

int main(int argc, char *argv[]) {
    return run({argv, argv + argc});
}

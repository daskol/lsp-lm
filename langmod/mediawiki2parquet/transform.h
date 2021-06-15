#pragma once

#include <filesystem>
#include <fstream>
#include <iostream>
#include <optional>
#include <string>
#include <vector>

namespace mediawiki {

namespace fs = std::filesystem;

/**
 * Enumeration FileType represents supported formats of source files.
 */
enum class FileType {
    Unknown,
    BZip2,
    XML,
};

std::istream &operator>>(std::istream &is, FileType &ft);

std::ostream &operator<<(std::ostream &os, FileType ft);

std::optional<FileType> ParseFileType(std::string_view view);

FileType GuessFileType(std::ifstream &ifs);

FileType GuessFileType(std::istream &is);

FileType GuessFileType(std::string const &filename);

/**
 * Function Transform reads XML dump, extract pages and store them to Parquet
 * file.
 */
size_t Transform(std::string const &src, std::string const &dst);

/**
 * Function Transform converts concurrently multiple Wikipedia dump partition
 * to Parquet files.
 */
size_t Transform(std::vector<fs::path> const &srcs, std::vector<fs::path> const &dsts, size_t nothreads = 0);

} // namespace mediawiki

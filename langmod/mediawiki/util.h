#pragma once

#include <chrono>
#include <string>
#include <optional>

namespace mediawiki {

/**
 * Function ParseTimestamp parses a timestring against known MediaWiki
 * timestamps formats (e.g. `%Y%m%d%H%M%S` and `%Y-%m-%dT%H:%M:%SZ`).
 */
std::optional<std::chrono::milliseconds> ParseTimestamp(std::string const &str) noexcept;

/**
 * Function ParseUInt64 parses unsigned 64-bits integer from string.
 */
std::optional<uint64_t> ParseUInt64(std::string const &str) noexcept;

} // namespace mediawiki

#include "util.h"

#include <ctime>
#include <iomanip>
#include <sstream>

namespace mediawiki {

std::optional<std::chrono::milliseconds> ParseTimestamp(std::string const &str, std::string const &fmt) {
    std::stringstream ss(str);
    std::tm tm = {};

    ss >> std::get_time(&tm, fmt.c_str());
    if (ss.fail()) {
        return std::nullopt;
    }

    using namespace std::chrono;
    auto tp = system_clock::from_time_t(std::mktime(&tm));
    auto ts = duration_cast<milliseconds>(tp.time_since_epoch());
    return ts;
}

inline auto ParseTimestampLong(std::string const &str) {
    return ParseTimestamp(str, "%Y-%m-%dT%H:%M:%SZ");
}

inline auto ParseTimestampShort(std::string const &str) {
    return ParseTimestamp(str, "%Y%m%d%H%M%S");
}

std::optional<std::chrono::milliseconds> ParseTimestamp(std::string const &str) noexcept {
    if (auto ts = ParseTimestampLong(str); ts) {
        return ts;
    } else if (auto ts = ParseTimestampShort(str); ts) {
        return ts;
    } else {
        return std::nullopt;
    }
}

std::optional<uint64_t> ParseUInt64(std::string const &str) noexcept {
    char *end;
    uint64_t val = std::strtoull(str.c_str(), &end, 10);
    return str.c_str() == end ? std::nullopt : std::optional<uint64_t>{val};
}

} // namespace mediawiki

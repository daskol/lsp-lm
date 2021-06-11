#pragma once

#include <memory>
#include <string>

#include <parquet/schema.h>
#include <parquet/stream_writer.h>

#include <langmod/mediawiki/wiki.h>

namespace mediawiki {

class PageWriter {
private:
    PageWriter(parquet::StreamWriter &&sw) noexcept
        : sw_{std::move(sw)}
    {}

public:
    void Write(Page const &page);

public:
    static std::shared_ptr<PageWriter> Create(std::string const &filename);

    /**
     * GetSchema defines schema for Wikipedia dump in Parquet file format.
     */
    static std::shared_ptr<parquet::schema::GroupNode> GetSchema(void);

private:
    parquet::StreamWriter sw_;
};

} // namespace mediawiki

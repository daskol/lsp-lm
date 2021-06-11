#include "writer.h"

#include <arrow/io/file.h>
#include <parquet/exception.h>

namespace mediawiki {

template <typename T>
inline parquet::StreamWriter::optional<T> optional_cast(std::optional<T> const &opt) {
    if (opt) {
        return *opt;
    } else {
        return {};
    }
}

void PageWriter::Write(Page const &page) {
    for (auto const &rev : page.revisions) {
        sw_ << page.title
            << page.ns
            << page.id
            << optional_cast(page.redirect)
            << optional_cast(page.restrictions)
            << rev.id
            << optional_cast(rev.parent_id)
            << rev.timestamp
            << optional_cast(rev.contributor.username)
            << optional_cast(rev.contributor.id)
            << optional_cast(rev.contributor.ip)
            << rev.minor
            << optional_cast(rev.comment)
            << rev.model
            << rev.format
            << rev.text
            << rev.sha1
            << parquet::EndRow;
    }
}

std::shared_ptr<PageWriter> PageWriter::Create(std::string const &filename) {
    parquet::WriterProperties::Builder builder;
    (&builder)
        ->compression(parquet::Compression::ZSTD)
        ->compression_level(9)
        ->created_by("mediawiki2parquet")
        ->data_page_version(parquet::ParquetDataPageVersion::V1)
        ->enable_statistics()
        ->max_row_group_length(1000)
        ->version(parquet::ParquetVersion::PARQUET_2_0)
        ->write_batch_size(16 << 20);

    auto aos = arrow::io::FileOutputStream::Open(filename);
    if (!aos.ok()) {
        throw std::runtime_error("failed to open destination file: " + filename);
    }

    auto os = parquet::StreamWriter(
        parquet::ParquetFileWriter::Open(*aos, GetSchema(), builder.build())
    );

    std::shared_ptr<PageWriter> res{new PageWriter(std::move(os))};
    return res;
}

std::shared_ptr<parquet::schema::GroupNode> PageWriter::GetSchema(void) {
    parquet::schema::NodeVector fields;

    // Append basic fields of Page type.

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "title", parquet::Repetition::REQUIRED, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "ns", parquet::Repetition::REQUIRED, parquet::Type::INT64,
        parquet::ConvertedType::UINT_64));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "id", parquet::Repetition::REQUIRED, parquet::Type::INT64,
        parquet::ConvertedType::UINT_64));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "redirect", parquet::Repetition::OPTIONAL, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "restrictions", parquet::Repetition::OPTIONAL, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    // Append flatten Revision fields.

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_id", parquet::Repetition::REQUIRED, parquet::Type::INT64,
        parquet::ConvertedType::UINT_64));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_parent_id", parquet::Repetition::OPTIONAL, parquet::Type::INT64,
        parquet::ConvertedType::UINT_64));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_timestamp", parquet::Repetition::REQUIRED, parquet::Type::INT64,
        parquet::ConvertedType::TIMESTAMP_MILLIS));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_contrib_username", parquet::Repetition::OPTIONAL, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_contrib_id", parquet::Repetition::OPTIONAL, parquet::Type::INT64,
        parquet::ConvertedType::UINT_64));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_contrib_ip", parquet::Repetition::OPTIONAL, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_minor", parquet::Repetition::REQUIRED, parquet::Type::BOOLEAN));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_comment", parquet::Repetition::OPTIONAL, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_model", parquet::Repetition::REQUIRED, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_format", parquet::Repetition::REQUIRED, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_text", parquet::Repetition::REQUIRED, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    fields.push_back(parquet::schema::PrimitiveNode::Make(
        "rev_sha1", parquet::Repetition::REQUIRED, parquet::Type::BYTE_ARRAY,
        parquet::ConvertedType::UTF8));

    // TODO: Do we need to save discussion threading info?

    return std::static_pointer_cast<parquet::schema::GroupNode>(
        parquet::schema::GroupNode::Make("schema", parquet::Repetition::REQUIRED, fields));
}

} // namespace mediawiki

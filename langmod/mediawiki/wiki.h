/**
 * \file wiki.h
 */

#pragma once

#include <chrono>
#include <iostream>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include <expat.h>

namespace mediawiki {

class Parser;

class Listener {
public:
    Listener(void) = delete;

    Listener(Parser &parser) noexcept
        : parser_{parser}
    {}

    virtual ~Listener(void) = default;

protected:
    Parser &GetParser(void) noexcept {
        return parser_;
    }

public:
    virtual void *Get(void) {
        return nullptr;
    }

public:
    virtual void HandleCharacterData(std::string_view text) = 0;

    virtual void HandleElementBegin(std::string_view elem, std::span<char const *> attrs) = 0;

    virtual void HandleElementEnd(std::string_view elem) = 0;

private:
    Parser &parser_;
};

/**
 * Class Parser wraps low-level generic implementation of XML parser. It
 * exposes only required callbacks.
 */
class Parser {
public:
    Parser(std::istream &is, std::size_t buflen = 4096);

    ~Parser(void);

    bool Parse(void);

    bool Resume(void);

    bool Suspend(void);

    bool Walk(Listener &listener);

private:
    static void HandleCharacterData(void *userdata, XML_Char const *ptr, int len);

    static void HandleElementBegin(void *userdata, XML_Char const *name, XML_Char const **attrs);

    static void HandleElementEnd(void *userdata, XML_Char const *name);

private:
    std::istream &is_;
    std::unique_ptr<char[]> buffer_;
    std::size_t buflen_;
    Listener *listener_ = nullptr;
    XML_Parser parser_ = nullptr;
};

/**
 * Struct Namespace corresponds to mw:NamespaceType in XSD of Wikipedia XMP
 * dump.
 */
struct Namespace {
    int64_t key;
    std::string case_;
    std::string name;
};

/**
 * Struct SiteInfo corresponds to mw:SiteInfoType in XSD of Wikipedia XMP dump.
 */
struct SiteInfo {
    std::string sitename;
    std::string dbname;
    std::string base;
    std::string generator;
    std::string case_;
    std::vector<Namespace> namespaces;
};

/**
 * Struct Contributor corresponds to mw:Contributor in XSD of Wikipedia XMP
 * dump.
 */
struct Contributor {
    std::optional<std::string> username;
    std::optional<std::uint64_t> id;
    std::optional<std::string> ip;
    bool deleted = false;
};

std::ostream &operator<<(std::ostream &os, Contributor const &cont);

/**
 * Struct Revision corresponds to mw:RevisionType in XSD of Wikipedia XMP dump.
 */
struct Revision {
    std::uint64_t id = 0ull;
    std::optional<std::uint64_t> parent_id; // Zero menas no parent.
    std::chrono::milliseconds timestamp;
    Contributor contributor;
    bool minor = false;
    std::optional<std::string> comment;
    std::string model;
    std::string format;
    std::string text;
    std::string sha1;
};

std::ostream &operator<<(std::ostream &os, Revision const &rev);

/**
 * Struct Upload corresponds to mw:UploadType in XSD of Wikipedia XMP dump.
 */
struct Upload {
    std::chrono::milliseconds timestamp;
    Contributor contributor;
    std::string comment;
    std::string filename;
    std::string src;
    std::uint64_t size;
};

/**
 * Struct DiscussionThreadingInfo corresponds to mw:DiscussionThreadingInfoType
 * in XSD of Wikipedia XMP dump.
 */
struct DiscussionThreadingInfo {
    std::string thread_subject;
    std::string thread_page;
    std::string thread_author;
    std::string thread_edit_status;
    std::string thread_type;
    std::uint64_t thread_parent;
    std::uint64_t thread_ancestor;
    std::uint64_t thread_id;
};

/**
 * Struct Page corresponds to mw:PageType in XSD of Wikipedia XMP dump.
 */
struct Page {
    std::string title;
    std::uint64_t ns = 0ull;
    std::uint64_t id = 0ull;
    std::optional<std::string> redirect = std::nullopt;
    std::optional<std::string> restrictions = std::nullopt;

    std::vector<Revision> revisions;
    std::vector<Upload> uploads;

    std::optional<DiscussionThreadingInfo> dti;
};

class SiteInfoListener : public Listener {
private:
    enum class State {
        SiteInfoBegin,
        SiteName,
        DBName,
        Base,
        Generator,
        Case,
        Namespaces,
        SiteInfoEnd,
    };

public:
    SiteInfoListener(Parser &parser) noexcept;

    SiteInfo GetSiteInfo(void);

    void HandleCharacterData(std::string_view text) override;

    void HandleElementBegin(std::string_view elem, [[maybe_unused]] std::span<char const *> attrs) override;

    void HandleElementEnd(std::string_view elem) override;

public:
    std::string text_;
    State state_ = State::SiteInfoBegin;
    SiteInfo info_;
};

class ContributorListener : public Listener {
private:
    enum class State {
        ContributorBegin,
        Username,
        ID,
        IP,
        ContributorEnd,
    };

public:
    ContributorListener(Parser &parser) noexcept;

    Contributor GetContributor(void);

    void HandleCharacterData(std::string_view text) override;

    void HandleElementBegin(std::string_view elem, std::span<char const *> attrs) override;

    void HandleElementEnd(std::string_view elem) override;

public:
    std::string text_;
    State state_ = State::ContributorBegin;
    Contributor contributor_;
};

class RevisionListener : public Listener {
private:
    enum class State {
        RevisionBegin,
        ID,
        ParentID,
        Timestamp,
        ContributorBegin,
        Contributor,
        ContributorEnd,
        Minor,
        Comment,
        Model,
        Format,
        Text,
        SHA1,
        RevisionEnd,
    };

public:
    RevisionListener(Parser &parser) noexcept;

    Revision GetRevision(void);

    void HandleCharacterData(std::string_view text) override;

    void HandleElementBegin(std::string_view elem, std::span<char const *> attrs) override;

    void HandleElementEnd(std::string_view elem) override;

private:
    std::string text_;
    State state_ = State::RevisionBegin;
    Revision revision_;
    ContributorListener contrib_listener_;
};

/**
 * PageListener parses XML subtree to Page structure.
 */
class PageListener : public Listener {
private:
    enum class State {
        PageBegin,
        Title,
        NS,
        ID,
        Redirect,
        Restrictions,
        AltRevisionUpload,
        Revision,
        RevisionBegin,
        RevisionEnd,
        Upload,
        UploadBegin,
        UploadEnd,
        DiscussionThreadingInfo,
        DiscussionThreadingInfoBegin,
        DiscussionThreadingInfoEnd,
        PageEnd,
    };

public:
    PageListener(Parser &parser) noexcept
        : Listener(parser)
        , contrib_listener_{parser}
        , rev_listener_{parser}
    {}

    Page GetPage(void);

    void HandleCharacterData(std::string_view text) override;

    void HandleElementBegin(std::string_view elem, std::span<char const *> attrs) override;

    void HandleElementEnd(std::string_view elem) override;

private:
    int32_t depth_ = 0;
    State state_ = State::PageBegin;
    std::string text_;
    Page page_;

    ContributorListener contrib_listener_;
    RevisionListener rev_listener_;
};

/// /**
///  * We assume that Type is a flat type which could be copied (sic!).
///  */
/// template <typename Type>
/// class TypeReader {
/// public:
///     TypeReader(std::istream &is, std::size_t buflen = 4096);
///
///     bool Next(void);
///
///     Type Read(void) {
///         auto ptr = reinterpret_cast<Type const *>(listener_.Get());
///         return Type(*ptr);
///     }
///
/// private:
///     Listener listener_;
///     Parser parser_;
/// };

class PageReader {
private:
    enum class State {
        Init,
        Next,
        Term,
    };

public:
    PageReader(std::istream &is, std::size_t buflen = 4096);

    bool Next(void);

    Page Read(void);

private:
    Parser parser_;
    State state_ = State::Init;
    PageListener listener_;
    Page page_;
};

} // namespace mediawiki

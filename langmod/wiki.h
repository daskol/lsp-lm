
#include <iostream>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include <expat.h>

namespace wiki {

std::optional<uint64_t> ParseUInt64(std::string const &str);

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

class PrintListener : public Listener {
public:
    PrintListener(Parser &parser) noexcept
        : Listener(parser)
    {}

    void HandleCharacterData(std::string_view text) override {
        std::cout << "[" << depth_ << "] char data:  " << text << '\n';
    }

    void HandleElementBegin(std::string_view elem, [[maybe_unused]] std::span<char const *> attrs) override {
        std::cout << "[" << depth_ << "] elem begin: " << elem << '\n';
        ++depth_;
    }

    void HandleElementEnd(std::string_view elem) override {
        --depth_;
        std::cout << "[" << depth_ << "] elem end:   " << elem << '\n';
    }

private:
    size_t depth_ = 0;
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

struct Namespace {
    int64_t key;
    std::string case_;
    std::string name;
};

struct SiteInfo {
    std::string sitename;
    std::string dbname;
    std::string base;
    std::string generator;
    std::string case_;
    std::vector<Namespace> namespaces;
};

struct Contributor {
    std::string username;
    std::uint64_t id = 0ull;
    std::string ip;
    bool deleted = false;
};

struct Revision {
    std::uint64_t id = 0ull;
    std::uint64_t parent_id = 0ull; // Zero menas no parent.
    std::string timestamp; // timestamp
    Contributor contributor;
    // TODO: Support field `minor`.
    std::string comment;
    std::string model;
    std::string format;
    std::string text;
    std::string sha1;
};

struct Page {
    std::string title;
    std::uint64_t ns = 0ull;
    std::uint64_t id = 0ull;
    std::optional<std::string> redirect = std::nullopt;

    Revision revision;
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
    SiteInfoListener(Parser &parser) noexcept
        : Listener(parser)
    {}

    SiteInfo GetSiteInfo(void) {
        return info_;
    }

    void HandleCharacterData(std::string_view text) override {
        switch (state_) {
        case State::SiteName:
        case State::DBName:
        case State::Base:
        case State::Generator:
        case State::Case:
            text_ += text;
            break;
        default:
            break;
        }
    }

    void HandleElementBegin(std::string_view elem, [[maybe_unused]] std::span<char const *> attrs) override {
        switch (state_) {
        case State::SiteInfoBegin:
            if (elem == "siteinfo") {
                state_ = State::SiteName;
                info_ = {};
            }
            break;
        case State::SiteName:
            if (elem == "sitename") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::DBName:
            if (elem == "dbname") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::Base:
            if (elem == "base") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::Generator:
            if (elem == "generator") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::Case:
            if (elem == "case") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::SiteInfoEnd:
            state_ = State::SiteInfoEnd;
            break;
        default:
            break;
        }
    }

    void HandleElementEnd(std::string_view elem) override {
        switch (state_) {
        case State::SiteName:
            info_.sitename = text_;
            state_ = State::DBName;
            break;
        case State::DBName:
            info_.dbname = text_;
            state_ = State::Base;
            break;
        case State::Base:
            info_.base = text_;
            state_ = State::Generator;
            break;
        case State::Generator:
            info_.generator = text_;
            state_ = State::Case;
            break;
        case State::Case:
            info_.case_ = text_;
            state_ = State::SiteInfoEnd;
            break;
        case State::SiteInfoEnd:
            if (elem == "siteinfo") {
                state_ = State::SiteInfoBegin;
            }
            break;
        default:
            break;
        }
    }

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
    ContributorListener(Parser &parser) noexcept
        : Listener(parser)
    {}

    Contributor GetContributor(void) {
        return contributor_;
    }

    void HandleCharacterData(std::string_view text) override {
        switch (state_) {
        case State::Username:
        case State::ID:
        case State::IP:
            text_ += text;
            break;
        default:
            break;
        }
    }

    void HandleElementBegin(std::string_view elem, std::span<char const *> attrs) override {
        switch (state_) {
        case State::ContributorBegin:
            if (elem == "contributor") {
                state_ = State::Username;
                contributor_ = {};
                for (auto const &attr : attrs) {
                    if (std::string_view(attr) == "deleted") {
                        contributor_.deleted = true;
                    }
                }
            }
            break;
        case State::Username:
            if (elem == "username") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::ID:
            if (elem == "id") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::IP:
            if (elem == "ip") {
                text_.resize(0);
                break;
            } else {
                [[fallthrough]];
            }
        case State::ContributorEnd:
            state_ = State::ContributorEnd;
        default:
            break;
        }
    }

    void HandleElementEnd(std::string_view elem) override {
        switch (state_) {
        case State::Username:
            contributor_.username = text_;
            state_ = State::ID;
            break;
        case State::ID:
            if (auto val = ParseUInt64(text_); val) {
                contributor_.id = *val;
                state_ = State::ID;
                break;
            } else {
                // TODO: Panic on failed conversion.
            }
            break;
        case State::IP:
            contributor_.ip = text_;
            state_ = State::ContributorEnd;
            break;
        case State::ContributorEnd:
            if (elem == "contributor") {
                state_ = State::ContributorBegin;
            }
            break;
        default:
            break;
        }
    }

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
    RevisionListener(Parser &parser) noexcept
        : Listener(parser)
        , contrib_listener_{parser}
    {}

    Revision GetRevision(void) {
        return revision_;
    }

    void HandleCharacterData(std::string_view text) override {
        switch (state_) {
        case State::ID:
        case State::ParentID:
        case State::Timestamp:
        case State::Minor:
        case State::Comment:
        case State::Model:
        case State::Format:
        case State::Text:
        case State::SHA1:
            text_ += text;
            break;
        case State::Contributor:
            contrib_listener_.HandleCharacterData(text);
            break;
        default:
            break;
        }
    }

    void HandleElementBegin(std::string_view elem, std::span<char const *> attrs) override {
        switch (state_) {
        case State::RevisionBegin:
            if (elem == "revision") {
                state_ = State::ID;
                // Try to avoid excessive allocation and move large buffers to
                // a clear structure.
                std::string text = std::move(revision_.text);
                revision_ = {};
                revision_.text = std::move(text);
                revision_.text.resize(0);
            }
            break;
        case State::ID:
            if (elem == "id") {
                text_.resize(0);
            }
            break;
        case State::ParentID:
            if (elem == "parentid") {
                text_.resize(0);
            } else {
                state_ = State::Timestamp;
            }
            [[fallthrough]];
        case State::Timestamp:
            if (elem == "timestamp") {
                text_.resize(0);
            }
            break;
        case State::ContributorBegin:
            if (elem == "contributor") {
                state_ = State::Contributor;
                contrib_listener_.HandleElementBegin(elem, attrs);
            }
            break;
        case State::Contributor:
            contrib_listener_.HandleElementBegin(elem, attrs);
            break;
        case State::Comment:
            if (elem == "comment") {
                text_.resize(0);
                break;
            } else {
                state_ = State::Model;
                [[fallthrough]];
            }
        case State::Model:
            if (elem == "model") {
                text_.resize(0);
            }
            break;
        case State::Format:
            if (elem == "format") {
                text_.resize(0);
            }
            break;
        case State::Text:
            if (elem == "text") {
                text_.resize(0);
                for (auto it = attrs.begin(); it != attrs.end(); ++it) {
                    if (std::string_view(*it) != "bytes") {
                        continue;
                    }
                    ++it;
                    if (auto val = ParseUInt64(*it); val) {
                        text_.reserve(*val);
                    }
                }
            }
            break;
        case State::SHA1:
            if (elem == "sha1") {
                text_.resize(0);
            }
            break;
        default:
            break;
        }
    }

    void HandleElementEnd(std::string_view elem) override {
        switch (state_) {
        case State::ID:
            if (auto val = ParseUInt64(text_); val) {
                revision_.id = *val;
                state_ = State::ParentID;
            }
            break;
        case State::ParentID:
            if (auto val = ParseUInt64(text_); val) {
                revision_.parent_id = *val;
                state_ = State::Timestamp;
            }
            break;
        case State::Timestamp:
            revision_.timestamp = text_;
            state_ = State::ContributorBegin;
            break;
        case State::Contributor:
            contrib_listener_.HandleElementEnd(elem);
            [[fallthrough]];
        case State::ContributorEnd:
            if (elem == "contributor") {
                revision_.contributor = contrib_listener_.GetContributor();
                state_ = State::Comment;
            }
            break;
        case State::Comment:
            if (elem == "comment") {
                revision_.comment = text_;
                state_ = State::Model;
            }
            break;
        case State::Model:
            revision_.model = text_;
            state_ = State::Format;
            break;
        case State::Format:
            revision_.format = text_;
            state_ = State::Text;
            break;
        case State::Text:
            revision_.text = text_;
            state_ = State::SHA1;
            break;
        case State::SHA1:
            revision_.sha1 = text_;
            state_ = State::RevisionEnd;
            break;
        case State::RevisionEnd:
            if (elem == "revision") {
                state_ = State::RevisionBegin;
            }
            break;
        default:
            break;
        }
    }

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
    enum class State : int {
        PageBegin,
        Title,
        NS,
        ID,
        Redirect,
        Restrictions,
        RevisionBegin,
        Revision,
        RevisionEnd,
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

} // namespace wiki

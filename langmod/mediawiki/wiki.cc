#include "wiki.h"

#include <cstdlib>

#include <langmod/mediawiki/util.h>

namespace mediawiki {

std::ostream &operator<<(std::ostream &os, Contributor const &cont) {
    os << "<Contributor";
    if (cont.username) {
        os << " username=" << *cont.username;
    }
    if (cont.id) {
        os << " id=" << *cont.id;
    }
    if (cont.ip) {
        os << " ip=" << *cont.ip;
    }
    return os << " deleted=" << std::boolalpha << cont.deleted << ">";
}

std::ostream &operator<<(std::ostream &os, Revision const &rev) {
    return os << "<Revision id=" << rev.id
              << " parent_id=" << (rev.parent_id ? *rev.parent_id : uint64_t())
              << " timestamp=" << rev.timestamp.count()
              << " contributor=" << rev.contributor
              << " minor=" << std::boolalpha << rev.minor
              << " model=" << rev.model
              << " format=" << rev.format
              << ">";
}

Parser::Parser(std::istream &is, size_t buflen)
    : is_{is}
    , buffer_{new char[buflen]}
    , buflen_{buflen}
    , parser_{XML_ParserCreate(nullptr)}
{
    XML_SetCharacterDataHandler(parser_, HandleCharacterData);
    XML_SetElementHandler(parser_, HandleElementBegin, HandleElementEnd);
    XML_SetUserData(parser_, this);
}

Parser::~Parser(void) {
    if (parser_) {
        XML_ParserFree(parser_);
    }
}

void Parser::HandleCharacterData(void *userdata, XML_Char const *ptr, int len) {
    reinterpret_cast<Parser *>(userdata)
        ->listener_
        ->HandleCharacterData({ptr, static_cast<size_t>(len)});
}

void Parser::HandleElementBegin(void *userdata, XML_Char const *name, XML_Char const **attrs) {
    size_t noattrs = 0;
    while (attrs[noattrs] != nullptr) {
        ++noattrs;
    }
    reinterpret_cast<Parser *>(userdata)
        ->listener_
        ->HandleElementBegin({name}, {attrs, noattrs});
}

void Parser::HandleElementEnd(void *userdata, XML_Char const *name) {
    reinterpret_cast<Parser *>(userdata)
        ->listener_
        ->HandleElementEnd(name);
}

bool Parser::Parse(void) {
    XML_Status status;
    do {
        size_t count = is_
            .read(buffer_.get(), buflen_)
            .gcount();
        status = XML_Parse(parser_, buffer_.get(), count, is_.eof());
    } while (!is_.eof() && status == XML_STATUS_OK);
    // TODO: Remove diagnostic reports.
    // auto code = XML_GetErrorCode(parser_);
    // std::cerr << "status: " << static_cast<int>(status);
    // if (status == XML_STATUS_ERROR) {
    //     std::cerr << " (" << static_cast<int>(code) << ") " << XML_ErrorString(code) << '\n';
    // } else {
    //     std::cerr << '\n';
    // }
    return status != XML_STATUS_ERROR;
}

bool Parser::Walk(Listener &listener) {
    listener_ = &listener;
    return Parse();
}

bool Parser::Resume(void) {
    switch (XML_ResumeParser(parser_)) {
    case XML_Status::XML_STATUS_ERROR:
        return false;
    case XML_Status::XML_STATUS_OK:
        return Parse();
    case XML_Status::XML_STATUS_SUSPENDED:
        return true;
    default:
        std::abort();
    }
}

bool Parser::Suspend(void) {
    return XML_StopParser(parser_, true) != XML_STATUS_ERROR;
}


SiteInfoListener::SiteInfoListener(Parser &parser) noexcept
    : Listener(parser)
{}

SiteInfo SiteInfoListener::GetSiteInfo(void) {
    return info_;
}

void SiteInfoListener::HandleCharacterData(std::string_view text) {
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

void SiteInfoListener::HandleElementBegin(std::string_view elem, [[maybe_unused]] std::span<char const *> attrs) {
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

void SiteInfoListener::HandleElementEnd(std::string_view elem) {
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

ContributorListener::ContributorListener(Parser &parser) noexcept
    : Listener(parser)
{}

Contributor ContributorListener::GetContributor(void) {
    return contributor_;
}

void ContributorListener::HandleCharacterData(std::string_view text) {
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

void ContributorListener::HandleElementBegin(std::string_view elem, std::span<char const *> attrs) {
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
            state_ = State::ID;
            [[fallthrough]];
        }
    case State::ID:
        if (elem == "id") {
            text_.resize(0);
            break;
        } else {
            state_ = State::IP;
            [[fallthrough]];
        }
    case State::IP:
        if (elem == "ip") {
            text_.resize(0);
            break;
        } else {
            state_ = State::ContributorEnd;
            [[fallthrough]];
        }
    case State::ContributorEnd:
    default:
        break;
    }
}

void ContributorListener::HandleElementEnd(std::string_view elem) {
    switch (state_) {
    case State::Username:
        if (elem == "username") {
            contributor_.username = text_;
            state_ = State::ID;
            break;
        } else {
            state_ = State::ID;
            [[fallthrough]];
        }
    case State::ID:
        if (elem == "id") {
            if (auto val = ParseUInt64(text_); val) {
                contributor_.id = *val;
                state_ = State::IP;
                break;
            } else {
                // TODO: Panic on failed conversion.
            }
            break;
        } else {
            state_ = State::IP;
            [[fallthrough]];
        }
    case State::IP:
        if (elem == "ip") {
            contributor_.ip = text_;
            state_ = State::ContributorEnd;
            break;
        } else {
            state_ = State::ContributorEnd;
            [[fallthrough]];
        }
    case State::ContributorEnd:
        if (elem == "contributor") {
            state_ = State::ContributorBegin;
            break;
        } else {
            [[fallthrough]];
        }
    default:
        // TODO: Handle appearence of an unexpected tag.
        break;
    }
}

RevisionListener::RevisionListener(Parser &parser) noexcept
    : Listener(parser)
    , contrib_listener_{parser}
{}

Revision RevisionListener::GetRevision(void) {
    return revision_;
}

void RevisionListener::HandleCharacterData(std::string_view text) {
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

void RevisionListener::HandleElementBegin(std::string_view elem, std::span<char const *> attrs) {
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
    case State::Minor:
        if (elem == "minor") {
            text_.resize(0);
            break;
        } else {
            [[fallthrough]];
        }
    case State::Comment:
        if (elem == "comment") {
            state_ = State::Comment;
            text_.resize(0);
            break;
        } else {
            [[fallthrough]];
        }
    case State::Model:
        if (elem == "model") {
            state_ = State::Model;
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

void RevisionListener::HandleElementEnd(std::string_view elem) {
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
        if (auto ts = ParseTimestamp(text_); ts) {
            revision_.timestamp = *ts;
            state_ = State::ContributorBegin;
            break;
        } else {
            // TODO: Handle timestamp parsing error.
            break;
        }
    case State::Contributor:
        contrib_listener_.HandleElementEnd(elem);
        [[fallthrough]];
    case State::ContributorEnd:
        if (elem == "contributor") {
            revision_.contributor = contrib_listener_.GetContributor();
            state_ = State::Minor;
        }
        break;
    case State::Minor:
        revision_.minor = true;
        state_ = State::Comment;
        break;
    case State::Comment:
        revision_.comment = text_;
        state_ = State::Model;
        break;
    case State::Model:
        if (elem == "model") {
            revision_.model = text_;
            state_ = State::Format;
        }
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

Page PageListener::GetPage(void) {
    return page_;
}

void PageListener::HandleCharacterData(std::string_view text) {
    switch (state_) {
    case State::Title:
    case State::NS:
    case State::ID:
    case State::Redirect:
    case State::Restrictions:
        text_ += text;
        break;
    case State::Revision:
        rev_listener_.HandleCharacterData(text);
        break;
    case State::Upload:
        // upload_listener_.HandleCharacterData(text);
        break;
    case State::DiscussionThreadingInfo:
        // dti_listener_.HandleCharacterData(text);
        break;
    default:
        // Do nothing for rest states.
        break;
    }
}

void PageListener::HandleElementBegin(std::string_view elem, [[maybe_unused]] std::span<char const *> attrs) {
    switch (state_) {
    case State::PageBegin:
        if (elem == "page") {
            state_ = State::Title;
            page_ = {};
        }
        break;
    case State::Title:
        if (elem == "title") {
            text_.resize(0);
        }
        break;
    case State::NS:
        if (elem == "ns") {
            text_.resize(0);
        }
        break;
    case State::ID:
        if (elem == "id") {
            text_.resize(0);
        }
        break;
    case State::Redirect:
        if (elem ==  "redirect") {
            for (auto it = attrs.begin(); it != attrs.end(); ++it) {
                if (std::string_view(*it) != "title") {
                    continue;
                }
                ++it;
                page_.redirect = *it;
                break;
            }
            break;
        } else {
            state_ = State::Restrictions;
            [[fallthrough]];
        }
    case State::Restrictions:
        if (elem == "restrictions") {
            text_.resize(0);
            break;
        } else {
            state_ = State::AltRevisionUpload;
            [[fallthrough]];
        }
    case State::AltRevisionUpload:
        if (elem == "revision") {
            state_ = State::Revision;
            rev_listener_.HandleElementBegin(elem, attrs);
            break;
        } else if (elem == "upload") {
            state_ = State::Upload;
            break;
        } else {
            state_ = State::DiscussionThreadingInfoBegin;
            [[fallthrough]];
        }
    case State::DiscussionThreadingInfoBegin:
        if (elem == "discussionthreadinginfo") {
            state_ = State::DiscussionThreadingInfo;
            break;
        } else {
            state_ = State::PageEnd;
            [[fallthrough]];
        }
    case State::PageEnd:
        break;
    case State::DiscussionThreadingInfo:
        // TODO: dti_listener_.HandleElementBegin(elem, attrs);
        break;
    case State::Revision:
        rev_listener_.HandleElementBegin(elem, attrs);
        break;
    case State::Upload:
        // TODO: upload_listener_.HandleElementBegin(elem, attrs);
        break;
    default:
        break;
    }

    ++depth_;
}

void PageListener::HandleElementEnd(std::string_view elem) {
    // Track depth of an element. Exit on </page> tag; otherwise throw an
    // error.
    if (--depth_ == 1) {
        if (elem == "page") {
            state_ = State::PageBegin;
            GetParser().Suspend();
            return;
        } else {
            // TODO: Handle error.
        }
    }

    // Handle parser state.
    switch (state_) {
    case State::Title:
        page_.title = text_;
        state_ = State::NS;
        break;
    case State::NS:
        if (auto val = ParseUInt64(text_); val) {
            page_.ns = *val;
            state_ = State::ID;
        } else {
            // TODO: Failed to parse uint64_t.
        }
        break;
    case State::ID:
        if (auto val = ParseUInt64(text_); val) {
            page_.id = *val;
            state_ = State::Redirect;
        } else {
            // TODO: Failed to parse uint64_t.
        }
        break;
    case State::Redirect:
        state_ = State::Restrictions;
        break;
    case State::Restrictions:
        page_.restrictions = text_;
        state_ = State::AltRevisionUpload;
        break;
    case State::Revision:
        rev_listener_.HandleElementEnd(elem);
        [[fallthrough]];
    case State::RevisionEnd:
        if (elem == "revision") {
            page_.revisions.push_back(rev_listener_.GetRevision());
            state_ = State::AltRevisionUpload;
        }
        break;
    case State::Upload:
        // upload_listener_.HandleElementEnd(elem);
        [[fallthrough]];
    case State::UploadEnd:
        if (elem == "upload") {
            state_ = State::AltRevisionUpload;
        }
        break;
    case State::DiscussionThreadingInfo:
        // dti_listener_.HandleElementEnd(elem);
        [[fallthrough]];
    case State::DiscussionThreadingInfoEnd:
        if (elem == "discussionthreadinginfo") {
            state_ = State::PageEnd;
        }
        break;
    case State::PageEnd:
        if (elem == "page") {
            state_ = State::PageBegin;
            GetParser().Suspend();
        }
        break;
    default:
        break;
    }
}

PageReader::PageReader(std::istream &is, std::size_t buflen)
    : parser_{is, buflen}
    , listener_{parser_}
{}

bool PageReader::Next(void) {
    switch (state_) {
    case State::Init:
        if (parser_.Walk(listener_)) {
            page_ = listener_.GetPage();
            state_ = State::Next;
            return true;
        } else {
            state_ = State::Term;
            return false;
        }
    case State::Next:
        if (parser_.Resume()) {
            page_ = listener_.GetPage();
            return true;
        } else {
            state_ = State::Term;
            return false;
        }
    case State::Term:
        return false;
    default:
        std::abort();
    }
}

Page PageReader::Read(void) {
    return page_;
}

} // namespace mediawiki

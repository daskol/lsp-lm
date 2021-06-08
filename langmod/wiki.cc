#include <cstdlib>

#include "wiki.h"

namespace wiki {

std::optional<uint64_t> ParseUInt64(std::string const &str) {
    char *end;
    uint64_t val = std::strtoull(str.c_str(), &end, 10);
    return str.c_str() == end ? std::nullopt : std::optional<uint64_t>{val};
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

Page PageListener::GetPage(void) {
    return page_;
}

void PageListener::HandleCharacterData(std::string_view text) {
    switch (state_) {
    case State::Title:
    case State::NS:
    case State::ID:
        text_ += text;
        break;
    case State::Revision:
        rev_listener_.HandleCharacterData(text);
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
            [[fallthrough]];
        }
    case State::RevisionBegin:
        if (elem == "revision") {
            state_ = State::Revision;
            rev_listener_.HandleElementBegin(elem, attrs);
        }
        break;
    case State::Revision:
        rev_listener_.HandleElementBegin(elem, attrs);
        break;
    default:
        break;
    }
}

void PageListener::HandleElementEnd(std::string_view elem) {
    switch (state_) {
    case State::Title:
        page_.title = std::move(text_);
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
        state_ = State::RevisionBegin;
        break;
    case State::Revision:
        rev_listener_.HandleElementEnd(elem);
        if (elem == "revision") {
            page_.revision = rev_listener_.GetRevision();
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

} // namespace wiki

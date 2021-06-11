set(CMAKE_CXX_STANDARD 20)

find_package(expat REQUIRED)

add_library("langmod-mediawiki" STATIC)

target_sources("langmod-mediawiki"
    PRIVATE util.cc
    PRIVATE util.h
    PRIVATE wiki.cc
    PUBLIC wiki.h
)

target_link_libraries("langmod-mediawiki"
    INTERFACE expat::expat
)

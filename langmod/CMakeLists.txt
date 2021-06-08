find_package(expat REQUIRED)

set(CMAKE_CXX_STANDARD 20)

add_executable("wiki2parquet")

target_sources("wiki2parquet"
    PRIVATE main.cc
    PRIVATE wiki.cc
    PUBLIC wiki.h
)

target_link_libraries("wiki2parquet"
    PRIVATE expat::expat
)

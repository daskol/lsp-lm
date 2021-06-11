set(CMAKE_CXX_STANDARD 20)

find_package(Arrow REQUIRED CONFIG)
find_package(Parquet REQUIRED CONFIG PATHS ${Arrow_DIR})

add_executable("mediawiki2parquet")

target_sources("mediawiki2parquet"
    PRIVATE main.cc
    PRIVATE writer.cc
    PRIVATE writer.h
)

target_link_libraries("mediawiki2parquet"
    PRIVATE arrow_shared
    PRIVATE langmod-mediawiki
    PRIVATE parquet_shared
)

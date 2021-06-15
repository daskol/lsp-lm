set(CMAKE_CXX_STANDARD 20)

find_package(Arrow REQUIRED CONFIG)
find_package(Threads REQUIRED)
find_package(BZip2 REQUIRED)
find_package(Parquet REQUIRED CONFIG PATHS ${Arrow_DIR})

add_executable("mediawiki2parquet")

target_sources("mediawiki2parquet"
    PRIVATE bz2.cc
    PRIVATE bz2.h
    PRIVATE main.cc
    PRIVATE queue.cc
    PRIVATE queue.h
    PRIVATE transform.cc
    PRIVATE transform.h
    PRIVATE writer.cc
    PRIVATE writer.h
)

target_link_libraries("mediawiki2parquet"
    PRIVATE BZip2::BZip2
    PRIVATE Threads::Threads
    PRIVATE arrow_shared
    PRIVATE langmod-mediawiki
    PRIVATE parquet_shared
)

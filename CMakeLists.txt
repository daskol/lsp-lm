cmake_minimum_required(VERSION 3.16)

project("langmod" VERSION 0.0.0 LANGUAGES CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_LINK_DEPENDS_NO_SHARED ON)
set(CMAKE_CONFIGURATION_TYPES
    "RelWithDebInfo;Debug;Release;MinSizeRel;ASan;TSan"
    CACHE STRING "" FORCE)

if (NOT CMAKE_BUILD_TYPE OR CMAKE_BUILD_TYPE STREQUAL "None")
    message(STATUS "Var CMAKE_BUILD_TYPE is not set, set to RelWithDebInfo")
    set(CMAKE_BUILD_TYPE "RelWithDebInfo")
endif()

include("cmake/BuildType.cmake")

include_directories("${CMAKE_CURRENT_SOURCE_DIR}")

if (CMAKE_GENERATOR STREQUAL "Ninja")
    add_compile_options(-fdiagnostics-color=always)
endif()

add_compile_options(-Wall -Wextra)

add_subdirectory("langmod")

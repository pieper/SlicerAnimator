cmake_minimum_required(VERSION 3.5)

project(Animator)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "http://slicer.org/slicerWiki/index.php/Documentation/Nightly/Extensions/Animator")
set(EXTENSION_CATEGORY "Wizards")
set(EXTENSION_CONTRIBUTORS "Steve Pieper (Isomics, Inc.)")
set(EXTENSION_DESCRIPTION "This is a high-level animation interface that operates on top of the Sequences and Screen Capture interfaces.")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/Animator.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/Animator/Screenshots/1.png")
set(EXTENSION_DEPENDS "Sequences") # Specified as a space separated string, a list or 'NA' if any

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(Animator)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})

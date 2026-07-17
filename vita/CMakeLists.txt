cmake_minimum_required(VERSION 3.16)

if(NOT DEFINED CMAKE_TOOLCHAIN_FILE)
  if(DEFINED ENV{VITASDK})
    set(CMAKE_TOOLCHAIN_FILE "$ENV{VITASDK}/share/vita.toolchain.cmake"
        CACHE PATH "Vita toolchain file")
  else()
    message(FATAL_ERROR "Please define VITASDK to point to your SDK path")
  endif()
endif()

project(vita_gamepad C)
include("${VITASDK}/share/vita.cmake" REQUIRED)

set(VITA_APP_NAME "Vita Gamepad")
set(VITA_TITLEID "VITAPAD01")
set(VITA_VERSION "01.00")

add_executable(vita-gamepad src/main.c)
target_compile_options(vita-gamepad PRIVATE -Wall -Wextra -Werror -O2)
target_link_libraries(vita-gamepad
  vita2d
  SceDisplay_stub
  SceGxm_stub
  SceSysmodule_stub
  SceCtrl_stub
  SceTouch_stub
  SceNet_stub
  SceNetCtl_stub
  ScePgf_stub
  SceCommonDialog_stub
  SceAppMgr_stub
  m
)

vita_create_self(vita-gamepad.self vita-gamepad UNSAFE)
vita_create_vpk(vita-gamepad.vpk ${VITA_TITLEID} vita-gamepad.self
  VERSION ${VITA_VERSION}
  NAME ${VITA_APP_NAME}
)

#!/usr/bin/env bash
# **وضعُ النظام في محاكي أندرويد** — `light` أو `dark` (نظيرُ `simctl ui appearance` في iPhone)
case "$1" in dark) adb shell cmd uimode night yes ;; *) adb shell cmd uimode night no ;; esac

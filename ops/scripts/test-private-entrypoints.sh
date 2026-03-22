#!/usr/bin/env bash
set -euo pipefail

loopback_url="${1:-http://127.0.0.1:8443}"
canonical_url="${2:-http://192.168.1.2:8443}"
login_path="/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"

loopback_headers="$(curl --noproxy '*' -I -sS --max-time 10 "${loopback_url}" | tr -d '\r')"
canonical_headers="$(curl --noproxy '*' -I -sS --max-time 10 "${canonical_url}" | tr -d '\r')"
loopback_login_html="$(curl --noproxy '*' -sS --max-time 10 "${loopback_url}${login_path}")"
canonical_login_html="$(curl --noproxy '*' -sS --max-time 10 "${canonical_url}${login_path}")"

if printf '%s\n' "${loopback_headers}" | grep -Eqi '^Location: http://192\.168\.1\.2:8443/?$'; then
  echo "loopback entry redirects to canonical host"
  exit 1
fi

if ! printf '%s\n' "${loopback_headers}" | grep -q '^HTTP/1\.1 '; then
  echo "loopback entry did not return an HTTP response"
  exit 1
fi

if ! printf '%s\n' "${canonical_headers}" | grep -q '^HTTP/1\.1 '; then
  echo "canonical entry did not return an HTTP response"
  exit 1
fi

if printf '%s\n' "${loopback_login_html}" | grep -q 'http://192\.168\.1\.2:8443'; then
  echo "loopback login page still leaks canonical host"
  exit 1
fi

if ! printf '%s\n' "${loopback_login_html}" | grep -q '<form'; then
  echo "loopback login page did not render the login form"
  exit 1
fi

if ! printf '%s\n' "${canonical_login_html}" | grep -q '<form'; then
  echo "canonical login page did not render the login form"
  exit 1
fi

echo "private entrypoints ok"

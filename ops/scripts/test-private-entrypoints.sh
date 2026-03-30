#!/usr/bin/env bash
set -euo pipefail

noncanonical_host="${1:-127.0.0.1}"
canonical_url="${2:-http://localhost:8443}"
login_path="/index.php?title=%E7%89%B9%E6%AE%8A:%E7%94%A8%E6%88%B7%E7%99%BB%E5%BD%95"

noncanonical_headers="$(curl --noproxy '*' -I -sS --max-time 10 -H "Host: ${noncanonical_host}" "${canonical_url}" | tr -d '\r')"
canonical_headers="$(curl --noproxy '*' -I -sS --max-time 10 "${canonical_url}" | tr -d '\r')"
noncanonical_login_headers="$(curl --noproxy '*' -I -sS --max-time 10 -H "Host: ${noncanonical_host}" "${canonical_url}${login_path}" | tr -d '\r')"
canonical_login_html="$(curl --noproxy '*' -L -sS --max-time 10 "${canonical_url}${login_path}")"

if ! printf '%s\n' "${noncanonical_headers}" | grep -q '^HTTP/1\.1 '; then
  echo "noncanonical host did not return an HTTP response"
  exit 1
fi

if ! printf '%s\n' "${canonical_headers}" | grep -q '^HTTP/1\.1 '; then
  echo "canonical entry did not return an HTTP response"
  exit 1
fi

if ! printf '%s\n' "${noncanonical_headers}" | grep -Eqi '^HTTP/1\.1 30[1278] '; then
  echo "noncanonical host did not redirect to the canonical host"
  exit 1
fi

if ! printf '%s\n' "${noncanonical_headers}" | grep -Eqi '^Location: http://localhost:8443/?$'; then
  echo "noncanonical host did not point to the canonical localhost host"
  exit 1
fi

if ! printf '%s\n' "${noncanonical_login_headers}" | grep -q "^Location: http://localhost:8443${login_path}$"; then
  echo "noncanonical login request did not redirect to the canonical host"
  exit 1
fi

if ! printf '%s\n' "${canonical_login_html}" | grep -q '<form'; then
  echo "canonical login page did not render the login form"
  exit 1
fi

echo "private entrypoints ok"

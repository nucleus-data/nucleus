---
title: Corporate Proxy
description: Using Nucleus behind a corporate proxy (Bosch, SAP, banks, enterprises with SSL inspection).
---

# Corporate Proxy

Many enterprise networks (Bosch, SAP, large banks) run SSL inspection proxies that intercept HTTPS traffic and issue their own certificates. This breaks standard `pip install` and Docker pull commands.

## Symptoms

- `pip install` fails with `SSLError: CERTIFICATE_VERIFY_FAILED`
- `docker pull` fails with certificate errors
- `nucleus up` fails because Docker can't pull the SeaweedFS image

## pip configuration

### Option 1 — Set proxy environment variables

```bash
# Set these in your shell profile (.bashrc, .zshrc, or Windows env vars)
export HTTPS_PROXY=http://proxy.company.com:8080
export HTTP_PROXY=http://proxy.company.com:8080
export NO_PROXY=localhost,127.0.0.1

pip install -e ".[dev]"
```

### Option 2 — Add corporate CA certificate

```bash
# Bosch example: add the CA cert to pip's trust store
pip install --cert /path/to/company-ca.crt nucleus

# Or configure globally
pip config set global.cert /path/to/company-ca.crt
```

### Option 3 — Trusted host (less secure)

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e ".[dev]"
```

## Docker configuration

```json
// ~/.docker/config.json or Docker Desktop → Settings → Docker Engine
{
  "proxies": {
    "default": {
      "httpProxy": "http://proxy.company.com:8080",
      "httpsProxy": "http://proxy.company.com:8080",
      "noProxy": "localhost,127.0.0.1"
    }
  }
}
```

For corporate CA certificates in Docker, add the cert to Docker's CA bundle:

```bash
# Linux (Docker Engine)
sudo cp company-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
sudo systemctl restart docker
```

## Offline install

If network access is fully blocked, install from a pre-downloaded wheel bundle:

```bash
# On a machine with internet access:
pip download -r requirements.txt -d ./wheels/

# Copy ./wheels/ to the air-gapped machine, then:
pip install --no-index --find-links ./wheels/ nucleus
```

## nucleus up behind proxy

If `nucleus up` fails because Docker can't pull the SeaweedFS image, pull it manually first:

```bash
docker pull chrislusf/seaweedfs:3.73  # or the version in docker-compose.yml
```

Then `nucleus up` will use the cached image.

## Getting help

If none of these work, [open a GitHub issue](https://github.com/nucleus-data/nucleus/issues) with:
- Your OS and proxy type
- The exact error message
- What you've already tried

# TLS Certificates

This directory is mounted read-only into the `nginx` reverse-proxy
container at `/etc/nginx/certs` (see `docker-compose.prod.yml`). It is
gitignored (`*.pem`/`*.key`, see root `.gitignore`) — never commit a real
certificate or private key.

## Local / staging: self-signed certificate

Generate one with `scripts/generate-self-signed-cert.sh` (or manually):

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/certs/privkey.pem \
  -out nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

Browsers will show a certificate-trust warning for a self-signed cert —
expected for local/staging use, never acceptable for real production
traffic.

## Production: a real certificate

Use [certbot](https://certbot.eff.org/) (Let's Encrypt, free, auto-renewing)
or your organization's certificate authority. The reverse proxy's plain-HTTP
server block already serves `/.well-known/acme-challenge/` from
`/var/www/certbot` for the standard certbot HTTP-01 challenge flow — see
`docs/deployment-guide.md` for the full certbot container/renewal-cron
setup once you have a real domain pointed at this host.

Whatever the source, place the certificate chain at `fullchain.pem` and the
private key at `privkey.pem` in this directory, then reload nginx
(`docker compose -f docker-compose.prod.yml exec nginx nginx -s reload`).

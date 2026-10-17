# Pointing saptashatitika.com at the site

The site is hosted by GitHub Pages out of `docs/` on the `main` branch. All
links in the generated HTML are relative, so nothing in the code changes when
the domain changes. The only place the public hostname is written down is
`SITE_URL` in `base_html.py`, which feeds the canonical tags, the Open Graph
tags and `sitemap.xml`.

## Order matters

Do these in order. Adding the custom domain in GitHub **before** the DNS
records exist makes the site unreachable in the meantime, because GitHub stops
serving `yashkhasbage25.github.io/SaptaTeeka/` and starts redirecting it to a
domain that does not yet resolve.

### 1. DNS records

**On Cloudflare DNS, prefer this.** Cloudflare's CNAME flattening allows a
CNAME at the apex, which it resolves to A records when answering queries:

```
CNAME   @     yashkhasbage25.github.io.     (DNS only / grey cloud)
CNAME   www   yashkhasbage25.github.io.     (DNS only / grey cloud)
```

This is better than hardcoding A records, because GitHub's documentation warns
that apex A records break if GitHub ever changes its server IP addresses,
whereas a CNAME keeps resolving. Flattening gives bare-apex URLs *and* that
immunity, which plain A records cannot.

**On any other DNS provider**, the apex needs four A records, since ordinary
DNS forbids a CNAME at the zone apex:

```
A   @   185.199.108.153
A   @   185.199.109.153
A   @   185.199.110.153
A   @   185.199.111.153
```

Optionally the IPv6 equivalents, which GitHub recommends adding alongside the
A records rather than instead of them:

```
AAAA   @   2606:50c0:8000::153
AAAA   @   2606:50c0:8001::153
AAAA   @   2606:50c0:8002::153
AAAA   @   2606:50c0:8003::153
```

Note the CNAME target is the *account* host, `yashkhasbage25.github.io.`, with
no repository name and with the trailing dot.

With both the apex and `www` configured, GitHub Pages creates the redirect
between them automatically. Setting the custom domain to the bare apex means
`www` redirects to it, so every URL a reader sees is
`https://saptashatitika.com/...`.

Requests to the old `https://yashkhasbage25.github.io/SaptaTeeka/` address are
301-redirected to the custom domain by GitHub. Verified against live sites:
`twbs.github.io/bootstrap/` 301s to `getbootstrap.com`, and
`jekyll.github.io/jekyll/` to `jekyllrb.com`.

**If the DNS is on Cloudflare**, set these records to *DNS only* (grey cloud),
not proxied. The orange cloud breaks GitHub's certificate provisioning. TXT
records are never proxied, so they are unaffected either way.

### 2. Verify the domain against your GitHub account

Optional but worth doing: it prevents anyone else from ever claiming this
domain on their own GitHub Pages site if yours is disabled.

GitHub account settings -> Pages -> Add a domain. GitHub gives you a TXT
record of the form:

```
TXT   _github-pages-challenge-yashkhasbage25   <token>
```

### 3. Add the custom domain in the repository

Repository settings -> Pages -> Custom domain -> `saptashatitika.com` -> Save.

This writes a `CNAME` file to the root of the publishing source. Because this
site publishes from `docs/`, the file must be at `docs/CNAME` containing
exactly:

```
saptashatitika.com
```

A ready copy is at `docs/CNAME.pending` — rename it to `docs/CNAME` once DNS
has propagated, or just let the GitHub UI create it and `git pull`.

### 4. Enforce HTTPS

Same settings page. The checkbox stays greyed out until GitHub has issued the
certificate, which can take up to 24 hours after DNS resolves. Tick it as soon
as it becomes available; without it the site is reachable over plain HTTP.

### 5. The second domain

GitHub Pages accepts exactly one custom domain, so `saptashatiteeka.com`
cannot be a second `CNAME`. Redirect it instead, which also keeps the
canonical story clean:

- **On Cloudflare (free):** put the domain on Cloudflare DNS, add a single
  A record for `@` pointing anywhere (`192.0.2.1` is fine, it is never
  reached) with the proxy *on*, then add a Redirect Rule:
  incoming `saptashatiteeka.com/*` -> `https://saptashatitika.com/${1}`,
  status 301, preserve query string. Path-preserving, so deep links survive.
- **At the registrar:** most offer domain forwarding. Choose a 301 permanent
  redirect and make sure it forwards the path, not just the bare domain.

## After it is live

Verify the canonical host actually resolves and redirects as intended:

```bash
curl -sI https://saptashatitika.com            | head -1
curl -sI https://www.saptashatitika.com        | grep -i '^location'
curl -sI https://saptashatiteeka.com/kavacham.html | grep -i '^location'
curl -sI https://yashkhasbage25.github.io/SaptaTeeka/ | grep -i '^location'
curl -s  https://saptashatitika.com/sitemap.xml | head -3
```

The last two matter: the old `github.io` URL should 301 to the new domain, and
the sitemap should be reachable so it can be submitted to Google Search
Console.

## Changing the domain later

Edit `SITE_URL` in `base_html.py`, run `python converter.py`, update
`docs/CNAME`, and change the DNS. Nothing else refers to the hostname.

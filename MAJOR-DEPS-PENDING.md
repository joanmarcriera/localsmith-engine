# Major-version dependency upgrades — url-shortener APPLIED 2026-10-16 (was pending 2026-09-06)

Applied 2026-10-16: sqlite v1.58.0, libc v1.75.7, go-strftime v1.0.0; go build and go test pass (2 passed in 3 packages). projects/ is gitignored, so the go.mod change is local only.


Routine minor/patch dependency sweep found nothing to apply in
`projects/dashboard` (already current). In `projects/url-shortener`, the only
available bump is gated behind a major version:

- `modernc.org/sqlite` v1.43.0 → v1.58.0
- `modernc.org/libc` v1.66.10 → v1.75.7
- both require `github.com/ncruces/go-strftime` v1.0.0 (currently pinned v0.1.9,
  a pre-1.0 → 1.0 jump — treated as a breaking/major change, not auto-applied)

## Migration steps (not yet done)
1. `cd projects/url-shortener && go get github.com/ncruces/go-strftime@v1.0.0 modernc.org/sqlite@v1.58.0 modernc.org/libc@v1.75.7 && go mod tidy`
2. Check `go-strftime`'s changelog/release notes for v1.0.0 breaking changes
   (package API stabilization at 1.0 — skim for any renamed/removed functions
   used transitively via modernc.org/sqlite; url-shortener doesn't call
   go-strftime directly, so risk is likely low, but modernc.org/sqlite's own
   behavior around time formatting should be smoke-tested).
3. `go build ./... && go test ./...`, then exercise the url-shortener's
   date/time-dependent paths manually (redirect logging / expiry, if any use
   strftime formatting) before committing.

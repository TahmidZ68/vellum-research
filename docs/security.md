# Security Architecture

Vellum Research processes untrusted third-party webpages. The following defense-in-depth controls are enforced:

1. **Indirect Prompt Injection Isolation**:
   - Active HTML elements (`<script>`, `<style>`, `<iframe>`, hidden nodes) are stripped before extraction.
   - Extracted text is stripped of control characters and delimiter tags (`</untrusted_source_content>`).
   - Source content is passed to LLMs exclusively inside `<untrusted_source_content>` tags with explicit system instructions treating it as untrusted data.
2. **SSRF Protection (`app/core/security_url.py`)**:
   - Only `http://` and `https://` schemes are permitted.
   - Loopback, private (`10/8`, `172.16/12`, `192.168/16`), link-local (`169.254/16`), multicast, reserved IPs, `localhost`, `.local`, `.internal`, and cloud metadata endpoints are blocked.
   - DNS resolution is checked prior to connection, and redirects (`follow_redirects=False`) are validated at every hop up to `MAX_REDIRECTS`.
   - Strict timeouts (`EXTRACTION_TIMEOUT_SECONDS`) and byte limits (`MAX_EXTRACTION_BYTES`) are enforced.
3. **Read-Only Agent Capabilities**:
   - The research workflow has zero shell, filesystem, email, or external mutation tools.
4. **Authentication, Ownership & Quotas**:
   - Passwords hashed with `bcrypt`.
   - Short-lived JWT access tokens (`HS256`).
   - Ownership enforced on every project, run, report, source, follow-up, and export query.
   - Sliding-window rate limiting and daily per-user research quotas.
5. **Safe Frontend Rendering**:
   - Markdown is rendered via `react-markdown` + `rehype-sanitize` without raw HTML execution.

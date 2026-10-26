# Node.js / TypeScript

## Cara Memakai Aturan

- Gunakan daftar ini sebagai sinyal investigasi, bukan alasan otomatis membuat temuan.
- Tetap buktikan jalur runtime dan dampak konkret dari diff. Jangan laporkan style, typing preference, atau maintainability tanpa defect yang dapat dipicu.
- Laporkan temuan pada semua level severity. Hanya temuan pada level {{SEVERITY_SCOPE}} yang menggerakkan verdict dan dibuatkan issue; sisanya tetap ditulis sebagai temuan non-blocking.

## Arsitektur
1. Pisah layer tegas: handler/controller → service → repository. No business logic di route handler.
2. No god file (>800 baris). Pecah per domain/feature.
3. Dependency injection — no direct import concrete di service. Pakai constructor injection.
4. No circular dependency antar module.
5. Config via environment variable — no hardcode URL/port/credential di source.

## TypeScript
6. Wajib TypeScript strict mode (`strict: true` di tsconfig).
7. `any` adalah sinyal hilangnya type safety, bukan bug otomatis. Laporkan hanya bila nilai melintasi trust boundary atau menghasilkan jalur runtime/API-contract failure yang konkret; gunakan `unknown` lalu narrow atau tipe eksplisit sebagai perbaikan.
8. No type assertion `as` tanpa validasi runtime — pakai type guard atau schema validation.
9. Inferred return type pada public function bukan bug otomatis. Laporkan hanya bila perubahan benar-benar merusak kontrak publik/caller; explicit return type adalah hardening kontrak, bukan temuan mandiri.
10. No `// @ts-ignore` atau `// @ts-expect-error` tanpa komentar alasan.

## Error Handling
11. Async route handler wajib try/catch atau error middleware. No unhandled promise rejection.
12. No bare `catch (e)` tanpa handle — minimal log + rethrow atau return error response.
13. Express/Fastify: wajib global error handler middleware. No default HTML error page di production.
14. No `process.exit()` di handler — biarkan framework handle graceful shutdown.
15. Error message ke client no leak internal detail (stack trace, query, path).

## Keamanan
16. No hardcode API key/secret/password. Wajib env var atau secret manager.
17. SQL/NoSQL injection: wajib parameterized query atau ORM. No string concat di query.
18. Input validation wajib di boundary (Joi/Zod/class-validator). No trust raw `req.body`.
19. No `eval()`, `Function()`, `vm.runInNewContext()` dengan user input.
20. Rate limiting wajib di endpoint publik (login, register, API).
21. CORS: wajib whitelist origin eksplisit. No `origin: '*'` di production.
22. Helmet (atau equivalent security headers) wajib aktif.
23. No `console.log` data sensitif (token, password, PII).

## Performa
24. No blocking event loop: heavy computation pindah ke worker thread atau child process.
25. Stream untuk file besar — no `readFileSync` atau buffer seluruh file ke memory.
26. Database connection pool wajib dikonfigurasi — no create connection per request.
27. Response compression (gzip/brotli) wajib aktif.
28. No `await` di loop — pakai `Promise.all`/`Promise.allSettled` untuk parallel.

## Database
29. Parameterized query wajib — no string interpolation di SQL.
30. Transaction untuk operasi multi-table yang harus atomik.
31. N+1 query: no query di loop. Pakai JOIN atau batch fetch.
32. Wajib LIMIT di query yang return list. No unbounded SELECT.
33. Index pada kolom yang sering di-WHERE/ORDER BY.
34. Migration wajib reversible — sediakan `down` migration.

## Testing
35. Wajib unit test untuk service/business logic.
36. Integration test untuk endpoint kritis (auth, payment, data mutation).
37. No mock data atau test fixture tersisa di production code.
38. Test isolation — no shared mutable state antar test case.

## Dependency
39. Lock file (`package-lock.json` / `pnpm-lock.yaml`) wajib committed.
40. No unused dependency di `dependencies` — pindah ke `devDependencies` atau hapus.
41. No `postinstall` script yang download/execute arbitrary code.
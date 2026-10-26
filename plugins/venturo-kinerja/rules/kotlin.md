# Kotlin (Android)

## Cara Memakai Aturan

- Gunakan daftar ini sebagai sinyal investigasi, bukan alasan otomatis membuat temuan.
- Tetap buktikan jalur runtime dan dampak konkret dari diff. Jangan laporkan style, preferensi arsitektur, atau maintainability tanpa defect yang dapat dipicu.
- Laporkan temuan pada semua level severity. Hanya temuan pada level {{SEVERITY_SCOPE}} yang menggerakkan verdict dan dibuatkan issue; sisanya tetap ditulis sebagai temuan non-blocking.

## Arsitektur
1. Clean Architecture / MVVM / MVI. No UI urus logika bisnis.
2. Wajib StateFlow/SharedFlow untuk reactive state. No LiveData di domain/data layer.
3. Domain layer no import Android framework (`android.*`, `androidx.*`).
4. Use case / interactor untuk bisnis logik — no langsung repo di ViewModel.
5. No god ViewModel (>300 baris). Pecah per feature.

## Coroutine & Async
6. Wajib Coroutine. No RxJava di project baru.
7. No eksekusi berat di `Dispatchers.Main`. Pindah `Dispatchers.Default` (CPU) / `Dispatchers.IO` (I/O).
8. Batal operasi di `viewModelScope` / `lifecycleScope` — no `GlobalScope`.
9. No catch `CancellationException` — biarkan propagate untuk cancellation.
10. `withContext(Dispatchers.IO)` untuk DB/network call di suspend function.
11. `Flow.catch` wajib handle error — no unhandled exception di flow.

## Null Safety
12. No `!!` (force unwrap). Wajib `?.` atau `?:` (elvis).
13. No bocor `Context` Activity/Fragment ke ViewModel — pakai `Application` context kalau perlu.
14. `lateinit` hanya untuk dependency injection. No `lateinit` untuk nullable field.
15. `requireNotNull()` / `checkNotNull()` hanya di precondition yang memang harus crash.

## Compose
16. No oper ViewModel langsung ke composable dalam. Wajib State Hoisting — angkat state ke atas.
17. Composable parameter harus stable/immutable. No `List` mutable — pakai `ImmutableList` atau `persistentListOf`.
18. No side effect di luar `LaunchedEffect`/`SideEffect`/`DisposableEffect`.
19. No object allocation di parameter composable (lambda, object baru) — picu recomposition.
20. `remember` untuk komputasi mahal. `derivedStateOf` untuk derived value.
21. No `mutableStateOf` di luar `remember` — kehilangan state saat recomposition.

## Error Handling
22. No bare `catch (e: Exception)` tanpa rethrow `CancellationException`.
23. Sealed class untuk Result/State — no boolean flag.
24. Network error wajib handle: timeout, no connection, server error. Tampil pesan user-friendly.

## Keamanan
25. No hardcode API key/secret. Pakai `BuildConfig` atau encrypted storage.
26. No log data sensitif (token, password, PII).
27. `EncryptedSharedPreferences` untuk data sensitif — no plain SharedPreferences.

## Performa
28. `DiffUtil` / `ListAdapter` untuk RecyclerView — no `notifyDataSetChanged()`.
29. No komputasi berat di `onBindViewHolder` / composable `build`.
30. Image loading: Coil/Glide dengan proper sizing dan cache.
31. No memory leak: unregister listener/callback di `onDestroy`/`onCleared`.

## Database
32. Parameterized query wajib — no string concat di SQL (Room `@Query` atau Exposed DSL).
33. N+1 query: no query di loop. Pakai `IN` clause atau batch fetch.
34. Room: `@Transaction` untuk operasi multi-table atomik.
35. Database operation wajib di `Dispatchers.IO` — no query di Main thread.
36. Wajib `LIMIT` di query yang return list. No unbounded query.
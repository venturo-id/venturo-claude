# Flutter

## Cara Memakai Aturan

- Gunakan daftar ini sebagai sinyal investigasi, bukan alasan otomatis membuat temuan.
- Tetap buktikan jalur runtime dan dampak konkret dari diff. Jangan laporkan style, preferensi arsitektur, atau maintainability tanpa defect yang dapat dipicu.
- Laporkan temuan pada semua level severity. Hanya temuan pada level {{SEVERITY_SCOPE}} yang menggerakkan verdict dan dibuatkan issue; sisanya tetap ditulis sebagai temuan non-blocking.

## Arsitektur
1. Pisah UI/logika. State konsisten. Lapisan data no import UI. Logika modular, testable.
2. No business logic di Widget — pindah ke BLoC/Cubit/Provider/Riverpod/GetX.
3. Domain layer no import Flutter/package framework.
4. Repository pattern untuk data access — no direct API call di UI.

## Widget
5. No massive widget tree (build >80 baris). Ekstrak sub-widget.
6. Helper function yang return widget bukan bug otomatis. Laporkan hanya bila terbukti merusak lifecycle, identity/key, state ownership, atau granular rebuild; class widget terpisah adalah salah satu perbaikan, bukan kewajiban universal.
7. Wajib `const` constructor di widget stateless.
8. No widget rebuild tidak perlu — pakai `const`, `Selector`, atau granular state.
9. `ListView.builder`/`GridView.builder` wajib untuk list dinamis — no `Column` + `map`.

## State Management
10. No boolean flag soup (`isLoading`, `isError`, `hasData`). Pakai sealed class/enum state.
11. Tangani semua state: Loading, Error, Success, Empty. No missing case.
12. No `setState` di `initState` — pakai `WidgetsBinding.instance.addPostFrameCallback`.
13. State harus immutable — no mutasi langsung, buat copy baru.

## Error Handling
14. IO/Network wajib try/catch. Tampil error ramah ke user. No silent error.
15. No bare `catch (e)` tanpa handle — minimal log.
16. `Future` wajib handle error: `.catchError()` atau try/catch di async.

## Keamanan & Log
17. No `print()`/`log()` di prod. Wajib AppLogger/logger package.
18. No simpan rahasia di `SharedPreferences`. Pakai `flutter_secure_storage`.
19. Hapus hardcoded API key/secret/credential.
20. No `http://` di production — wajib HTTPS.

## Performa
21. Wajib `const` widget/constructor dimana bisa.
22. No komputasi berat di `build()` — pindah ke `initState`, BLoC, atau isolate.
23. Image: cache (`CachedNetworkImage`), resize sesuai display, format WebP.
24. No `Opacity` widget untuk hide — pakai `Visibility` atau conditional render.
25. `RepaintBoundary` untuk area yang sering repaint.

## Async & Lifecycle
26. Wajib `dispose()` semua: StreamController, AnimationController, TextEditingController, FocusNode.
27. No `BuildContext` setelah `await` tanpa `mounted` check.
28. Timer/periodic wajib cancel di `dispose()`.

## UI & Responsif
29. No px kaku. Pakai `Expanded`/`Flexible`/`MediaQuery`/`LayoutBuilder`.
30. Tema konsisten — wajib pakai `Theme.of(context)`, no hardcode warna.
31. Wajib support dark mode kalau ada di spec.

## Testing
32. Wajib unit test untuk logic/BLoC/Cubit.
33. No dead code atau mock data di production.
34. Widget test untuk interaksi kritis.

## Database
35. Parameterized query wajib — no string concat di SQL (sqflite/Drift).
36. N+1 query: no query di loop. Pakai batch fetch atau JOIN.
37. Database operation wajib di isolate atau async — no blocking UI thread.
38. Transaction untuk operasi multi-table atomik.
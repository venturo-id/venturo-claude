# iOS (Swift)

## Cara Memakai Aturan

- Gunakan daftar ini sebagai sinyal investigasi, bukan alasan otomatis membuat temuan.
- Daftar ini BUKAN checklist audit repo. Pada review diff, periksa aturan hanya pada baris yang diubah; jangan membuka file, target, atau build setting lain semata-mata untuk memverifikasi sebuah aturan (mis. aturan strict concurrency tidak berarti harus membaca `project.pbxproj` bila diff tidak menyentuhnya).
- Tetap buktikan jalur runtime dan dampak konkret dari diff. Jangan laporkan style, preferensi arsitektur, atau maintainability tanpa defect yang dapat dipicu.
- Laporkan temuan pada semua level severity. Hanya temuan pada level {{SEVERITY_SCOPE}} yang menggerakkan verdict dan dibuatkan issue; sisanya tetap ditulis sebagai temuan non-blocking.

## Arsitektur
1. Wajib MVVM/VIPER/TCA. No Massive View Controller (>300 baris).
2. Pisah UI/domain tegas. ViewController/View hanya render — no business logic.
3. No import UIKit/SwiftUI di domain/data layer.
4. Protocol-oriented design untuk dependency injection dan testability.
5. Coordinator/Router pattern untuk navigasi — no navigasi langsung dari ViewModel.

## Memori & Retain Cycle
6. Cegah strong reference cycle. Wajib `[weak self]` atau `[unowned self]` di closure.
7. Delegate wajib `weak`. No strong delegate reference.
8. No retain cycle di closure chain — cek setiap capture list.
9. `deinit` untuk verifikasi deallocation saat debug.
10. No strong reference ke parent dari child object.

## Threading
11. UI update wajib di Main Thread. Pakai `@MainActor` atau `DispatchQueue.main.async`.
12. Logika berat → background: `Task.detached`/`DispatchQueue.global(qos:)`. No block main thread.
13. No `DispatchQueue.main.sync` dari main thread (deadlock).
14. Kode baru wajib Swift Concurrency (async/await) over GCD.

## Swift Concurrency (Swift 6)
15. No data race. Shared mutable state wajib di-protect actor atau isolasi — no unsynchronized access.
16. Type yang cross actor/Task boundary wajib `Sendable`. No kirim non-Sendable reference antar isolation domain.
17. Closure cross-actor wajib `@Sendable` — no capture mutable state non-Sendable.
18. UI-facing type (ViewModel/View) wajib `@MainActor`. No update UI dari luar main actor.
19. Prefer structured concurrency (`async let`/`TaskGroup`) over `Task.detached`. Detached hanya bila benar-benar butuh lepas dari context.
20. `Task` wajib respect cancellation — cek `Task.isCancelled`/`try Task.checkCancellation()` dan cancel saat view hilang. No leaked task.
21. Sadar actor reentrancy — jangan asumsi state konsisten setelah `await` di dalam actor.
22. Migrasi completion handler lama → async/await untuk kode baru. Bungkus API lawas dengan `withCheckedContinuation` (no double-resume).
23. Aktifkan strict concurrency checking (Swift 6 mode). Resolusi warning isolation satu kategori per iterasi — no suppress massal.

## Optional & Error
24. No Force Unwrapping (`!`). Wajib `guard let`/`if let`.
25. Tangani error `do/try/catch`. No telan error (empty catch).
26. No `try!` / `as!` kecuali di test atau genuinely impossible failure.
27. Custom error type conform `LocalizedError` — no raw string error.
28. `Result<Success, Failure>` untuk async callback pattern (kode lawas).

## SwiftUI
29. Wajib `@State`/`@Binding`/`@StateObject`/`@ObservedObject` sesuai ownership.
30. `@StateObject` untuk create, `@ObservedObject` untuk inject dari parent.
31. Kode baru (iOS 17+) prefer `@Observable` (Observation framework) over `ObservableObject`. Gate dengan `#available` bila masih support < iOS 17.
32. No side effect di `body` getter — pakai `.onAppear`/`.task`.
33. Pecah View besar — hindari body >50 baris. Jaga view identity stabil untuk diffing efisien.
34. No deprecated API. Ganti `NavigationView` → `NavigationStack`, `onChange(of:perform:)` lawas → signature baru. Gate fitur versi-spesifik dengan `#available`.
35. `@Environment` untuk shared dependency — no singleton akses langsung.
36. Data visualization pakai Swift Charts, bukan custom drawing manual.

## UIKit (Legacy)
37. `prepareForReuse()` wajib reset state di custom cell.
38. No force cast `as!` di `cellForRowAt` — pakai `guard let as?`.
39. Auto Layout constraint no conflict — cek console warning.

## Keamanan
40. No hardcode API key/secret. Pakai Keychain atau secure config.
41. No log data sensitif (token, PII). Pakai `OSLog` dengan privacy level.
42. `URLSession` wajib HTTPS. No `NSAllowsArbitraryLoads` di production.
43. Certificate pinning untuk endpoint kritis.

## Performa
44. No komputasi berat di `viewDidLoad`/`body` — pindah ke background.
45. Image: resize sebelum display, cache dengan `NSCache` atau library.
46. `Instruments` untuk detect leak dan CPU spike — no ignored leak.
47. Prefetch data untuk `UITableView`/`UICollectionView` (`prefetchDataSource`).
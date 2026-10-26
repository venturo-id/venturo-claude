# React Native

## Cara Memakai Aturan

- Gunakan daftar ini sebagai sinyal investigasi, bukan alasan otomatis membuat temuan.
- Tetap buktikan jalur runtime dan dampak konkret dari diff. Jangan laporkan style, preferensi arsitektur, atau maintainability tanpa defect yang dapat dipicu.
- Laporkan temuan pada semua level severity. Hanya temuan pada level {{SEVERITY_SCOPE}} yang menggerakkan verdict dan dibuatkan issue; sisanya tetap ditulis sebagai temuan non-blocking.

## UI & List
1. No `ScrollView` untuk list dinamis/besar. Wajib `FlatList`/`SectionList`.
2. `FlatList`: wajib `keyExtractor` unik, `getItemLayout` kalau fixed height, `windowSize` tuning.
3. Wajib `StyleSheet.create` — no inline style object (buat objek baru tiap render).
4. No nesting `ScrollView` dalam `ScrollView` tanpa `nestedScrollEnabled`.
5. `removeClippedSubviews={true}` untuk list panjang off-screen.

## Navigasi
6. No kirim data raksasa via navigation params — kirim ID, fetch di screen tujuan.
7. Batasi deep nesting navigator. Flatten kalau bisa.
8. `useFocusEffect` untuk refresh data saat screen focus — no stale data.
9. Deep link wajib handle: parse, validate, fallback ke home kalau invalid.

## State & Data
10. Wajib TypeScript. No `any`. Props/state wajib typed.
11. No prop drilling >3 level — pakai Context/Zustand/Redux.
12. Server state pakai React Query/SWR — no manual fetch+setState.
13. No `setState` di unmounted component — pakai cleanup/abort.
14. Sensitive data: `react-native-keychain` / `expo-secure-store` — no `AsyncStorage`.

## Performa
15. `useMemo`/`useCallback` untuk props ke child — cegah re-render.
16. No `console.log` di production (blocking JS thread).
17. Heavy computation di `InteractionManager.runAfterInteractions` atau `requestAnimationFrame`.
18. Image: resize server-side, cache (`FastImage`), format WebP. Wajib `width`/`height`.
19. No inline function di `renderItem` — ekstrak atau `useCallback`.
20. `React.memo` untuk komponen list item.

## Native & Platform
21. `SafeAreaView` / `useSafeAreaInsets` untuk notch/status bar.
22. Platform spesifik: `.ios.tsx`/`.android.tsx` atau `Platform.select()`.
23. Permission request wajib handle denied/blocked — no crash, tampil fallback.
24. Keyboard handling: `KeyboardAvoidingView` atau `react-native-keyboard-aware-scroll-view`.
25. No hardcode dimensi — pakai `Dimensions`/`useWindowDimensions`/`%`.

## Aset & Media
26. Wajib atur aspect ratio/ukuran media. Pakai WebP.
27. Font custom: preload via config, no runtime load.
28. Icon: pakai vector icon library — no bitmap icon untuk UI standar.

## Error & Crash
29. Error boundary wajib di root dan per-section kritis.
30. Native crash reporting (Sentry/Crashlytics) wajib active di production.
31. Network error wajib handle: timeout, offline, retry. Tampil UI feedback.
32. No unhandled promise rejection — global handler wajib ada.

## Bridge & Native Module
33. No heavy data transfer lewat bridge dalam loop — batch kalau bisa.
34. Native module async method wajib return Promise — no callback hell.
35. `Hermes` engine wajib enabled untuk performance.
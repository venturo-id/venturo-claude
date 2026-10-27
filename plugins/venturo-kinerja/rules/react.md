# React

## Cara Memakai Aturan

- Gunakan daftar ini sebagai sinyal investigasi, bukan alasan otomatis membuat temuan.
- Tetap buktikan jalur runtime dan dampak konkret dari diff. Jangan laporkan style, preferensi arsitektur, atau maintainability tanpa defect yang dapat dipicu.
- Laporkan temuan pada semua level severity. Hanya temuan pada level {{SEVERITY_SCOPE}} yang menggerakkan verdict dan dibuatkan issue; sisanya tetap ditulis sebagai temuan non-blocking.

## Komponen
1. Pisah UI/logika. No komponen raksasa (>200 baris). Pecah jadi sub-komponen.
2. Cegah re-render: wajib `useMemo`/`useCallback` untuk props objek/fungsi ke child.
3. No inline object/array di JSX props (`style={{...}}` tiap render = objek baru).
4. Komponen list wajib `key` unik — no index sebagai key kecuali list statis.
5. No nested component definition (komponen dalam komponen = remount tiap render).

## Efek & State
6. `useEffect` dependency array wajib lengkap. No dependency palsu/hilang.
7. Wajib cleanup langganan/timer/listener di return `useEffect`.
8. No state untuk nilai yang bisa di-derive dari props/state lain.
9. No `setState` di `useEffect` tanpa kondisi guard (infinite loop risk).
10. Async di `useEffect`: wajib handle unmount (`AbortController` / flag `isMounted`).

## Tipe Data
11. Wajib TypeScript. No `any`. Pakai `unknown` lalu narrow.
12. Props wajib interface/type eksplisit — no implicit `any`.
13. Hindari prop drilling >3 level. Pakai Context API/Zustand/Jotai.
14. No enum, pakai string literal union.

## Keamanan
15. No `dangerouslySetInnerHTML` kecuali sanitize dulu (DOMPurify).
16. No manipulasi DOM langsung. Pakai `useRef`.
17. No `eval()`, `Function()`, atau dynamic script injection.
18. User input di URL/href wajib validasi (cegah `javascript:` protocol).

## Performa
19. Lazy load komponen berat: `React.lazy()` + `Suspense`.
20. No komputasi berat di render body — pindah ke `useMemo` atau di luar komponen.
21. Image wajib `width`/`height` eksplisit (cegah CLS).
22. No `console.log` di production code.

## Aksesibilitas
26. Wajib semantic HTML (`button`, `nav`, `main`, `section`) — no `div` + `onClick` tanpa `role`.
27. Interactive element wajib keyboard accessible — `onKeyDown`/`onKeyPress` atau native element.
28. Image wajib `alt` text. Decorative image: `alt=""` + `aria-hidden="true"`.
29. Form input wajib `label` (`htmlFor`) atau `aria-label`/`aria-labelledby`.
30. No color-only information indicator — tambah icon/text sebagai pendamping.
31. Focus management: modal/dialog wajib trap focus dan restore saat close.

## Testing
32. Wajib unit test untuk custom hooks dan utility functions.
33. No mock data atau test fixture tersisa di production code.
34. Komponen kritis (auth, form, payment) wajib integration test.
35. Test user interaction, bukan implementation detail — prefer `@testing-library/react`.

## Anti-Pattern
23. No `async forEach` — pakai `Promise.all` + `map` atau `for...of`.
24. No ternary bersarang >2 level di JSX — ekstrak ke variabel/fungsi.
25. No business logic di komponen — pisah ke custom hook atau service.
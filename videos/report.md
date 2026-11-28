# Шаг 4. Тестовые ролики (TEST_2026-11-28_1759)

seed: `81570` (повторить тот же монтаж: run с этим seed)

## 01_p_gloves_pov_organic
- organic, 9.7 с, 4 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black) → palm (gloves, black, руки gloves) → both (gloves, black) → loop (gloves, black, руки gloves)
- тексты: «Looks like a wallet.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.» → «Two colours.»
- 3D: переход нет, 3D-планы s_profile, s_two_colours, модель black, доля 3D 30 %
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: нет
- текст: «Looks like a wallet.» (`p_hook_06`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.4 dBTP; SFX: click «charge with taps.wav» 0.0 с, magnet «swoosh 2.wav» 1.9 с, whoosh «harsh whoosh 1.wav» 3.4 с, whoosh «swhoosh.wav» 6.8 с
- попыток: 3 (взята 2-я); луп SSIM: 0.988
- визуально (Claude): ❌ text_not_cut, text_matches_shot, first_frame_explains_product, looks_like_ad; В кадре 1 открытый кейс с презервативом показан, но второй презерватив не виден — «Holds 2» не подтверждено, первый кадр объясняет продукт лишь частично; Кадр 5: наплыв текста «Ultra-slim.» на полупрозрачный кейс выглядит как грязный кроссфейд, текст блёклый и плохо читается; Кадр 3: текст «Hidden magnetic closure.» частично перекрыт пальцами/перчаткой справа, замок не показан крупно
- проверка: ❌ визуально: text_not_cut, text_matches_shot, first_frame_explains_product, looks_like_ad

## Время

- нарезка: 2.5 мин
- рендер: 4.4 мин
- загрузка на Диск: 0.7 мин
- всего: 10.3 мин
- Claude (визуальная проверка): 3 запросов ≈ $0.041
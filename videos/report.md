# Шаг 4. Тестовые ролики (TEST_2026-11-28_1145)

seed: `59103` (повторить тот же монтаж: run с этим seed)

## 01_p_studio_to_life_organic
- organic, 8.1 с, 4 планов, цвет black, сетка 89 BPM
- fix-03: мир studio_paper 83 %, смен мира 1 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (studio_paper, black) → studio_closed (studio_paper, black) → street (street_hands, black, руки bare) → loop (studio_paper, black)
- тексты: «The condom case, redesigned.» → «Eco-leather. Ultra-slim.» → «Made to carry.»
- проверки: первая склейка 1.33 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.35 с, цена на экране: нет
- текст: «The condom case, redesigned.» (`p_hook_05`)
- исходники: 6796620381629818176.MP4, IMG_1386.MOV
- звук: музыка «ssstik.io_1795780819059», 89 BPM, с 5.2 с; -14.0 LUFS, пик -4.5 dBTP; SFX: click «clicks x3.wav» 0.0 с, whoosh «air.wav» 2.5 с
- попыток: 1; луп SSIM: 0.996
- визуально (Claude): ❌ text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, one_location, first_frame_explains_product, looks_like_ad, looks_cheap; В кадрах 1–2 текст «The condom case, redesigned.» перекрывает верхнюю часть кейса и частично закрывает его; Текстовые плашки — тяжёлые тёмно-серые прямоугольники, выглядят как шаблон, а не как нативный текст; В кадре 1 внутри видна только одна жёлтая упаковка, закрытая чёрной полосой — непонятно, что кейс вмещает 2 презерватива
- проверка: ❌ визуально: text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, one_location, first_frame_explains_product, looks_like_ad, looks_cheap

## 02_p_gloves_pov_organic
- organic, 7.8 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → loop (gloves, black, руки gloves)
- тексты: «Holds two. Nothing more.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: нет
- текст: «Holds two. Nothing more.» (`p_hook_10`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.6 dBTP; SFX: click «shutter clicks 1.wav» 0.0 с, magnet «swoosh 2.wav» 1.9 с
- попыток: 1; луп SSIM: 0.863
- визуально (Claude): ❌ shots_feel_continuous, text_matches_shot, looks_like_ad; В кадрах 1–2 на открытом кейсе виден только один презерватив, а текст «Holds two» обещает два — подпись не совпадает с кадром; Показан только чёрный цвет, второй цвет (Cognac Brown) нигде не появляется; В кадрах 5, 6, 7, 8 сверху виден тёмно-синий блок/полоса, края кадра выглядят неаккуратно, меняется фон и кадрирование
- проверка: ❌ визуально: shots_feel_continuous, text_matches_shot, looks_like_ad

## 03_p_gloves_pov_promote
- promote, 9.1 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → card (gloves, black, руки gloves)
- тексты: «Two condoms. One slim case.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: да
- текст: «Two condoms. One slim case.» (`p_hook_16`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.5 dBTP; SFX: click «gear click.wav» 0.0 с, magnet «charge with swoosh.wav» 1.9 с
- попыток: 1; луп SSIM: —
- визуально (Claude): ❌ text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, one_location, looks_cheap; Кадр 4: пустая тёмная плашка без текста; Кадр 6: текст «Looks like a mini wallet» частично сливается с фоном, слово «wallet» плохо читается; Кадр 1: кейс обрезан краями кадра, видна только одна сторона, видно один презерватив, а текст говорит «Two condoms»
- проверка: ❌ визуально: text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, one_location, looks_cheap

## Время

- нарезка: 9.9 мин
- рендер: 4.3 мин
- загрузка на Диск: 0.6 мин
- всего: 22.8 мин
- Claude (визуальная проверка): 9 запросов ≈ $0.120
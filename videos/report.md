# Шаг 4. Тестовые ролики (TEST_2026-11-28_1445)

seed: `69946` (повторить тот же монтаж: run с этим seed)

## 01_p_gloves_pov_organic
- organic, 7.8 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → loop (gloves, black, руки gloves)
- тексты: «Looks like a wallet.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: нет
- текст: «Looks like a wallet.» (`p_hook_06`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.7 dBTP; SFX: click «tap x4.wav» 0.0 с, magnet «box slide 1.wav» 1.9 с, whoosh «air.wav» 3.1 с
- попыток: 3 (взята 1-я); луп SSIM: 0.863
- визуально (Claude): ❌ text_not_cut, text_matches_shot, first_frame_explains_product, looks_like_ad; Первый кадр показывает открытый кейс только с одним презервативом, а не с двумя, поэтому «вмещает 2» не считывается; В кадре 7 текст «Looks like a mini wallet.» перекрыт верхним краем кейса, нижняя строка частично закрыта; В кадре 8 текст бледный и серый, контраст ниже, чем в других кадрах, читается хуже
- проверка: ❌ визуально: text_not_cut, text_matches_shot, first_frame_explains_product, looks_like_ad

## 02_p_studio_to_life_organic
- organic, 8.1 с, 4 планов, цвет cognac, сетка 89 BPM
- fix-03: мир studio_paper 83 %, смен мира 1 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (studio_paper, cognac) → studio_closed (studio_paper, cognac) → street (street_hands, cognac, руки bare) → loop (studio_paper, cognac)
- тексты: «Cognac Brown. Midnight Black.» → «Eco-leather. Ultra-slim.» → «Made to carry.»
- проверки: первая склейка 1.33 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.35 с, цена на экране: нет
- текст: «Cognac Brown. Midnight Black.» (`p_hook_18`)
- исходники: IMG_1440.MOV, IMG_1444.MOV, IMG_8801.MOV
- звук: музыка «ssstik.io_1795780819059», 89 BPM, с 7.9 с; -14.0 LUFS, пик -2.9 dBTP; SFX: click «phone tap 3.wav» 0.0 с, whoosh «box slide 1.wav» 2.4 с, whoosh «soft whoosh 2.wav» 2.4 с
- попыток: 3 (взята 1-я); луп SSIM: 0.982
- визуально (Claude): ❌ text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, first_frame_explains_product, looks_like_ad; Текст «Cognac Brown. Midnight Black.» в кадрах 1–2 перекрыт корпусом кейса — слова «Midnight Black» частично закрыты продуктом; Текст «Two colours» не соответствует кадру: виден только один цвет (коньячный), второго нет; В кадре 3 текст «Eco-leather. Ultra-slim.» перекрывается чёрной коробкой, слово «Ultra-slim» плохо читается
- проверка: ❌ визуально: text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, first_frame_explains_product, looks_like_ad

## 03_p_gloves_pov_promote
- promote, 9.1 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → card (gloves, black, руки gloves)
- тексты: «A condom case, finally done right.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: да
- текст: «A condom case, finally done right.» (`p_hook_09`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.6 dBTP; SFX: click «click x2.wav» 0.0 с, magnet «box slide 1.wav» 1.9 с, whoosh «soft whoosh 1.wav» 3.1 с
- попыток: 3 (взята 2-я); луп SSIM: —
- визуально (Claude): ❌ text_readable, text_not_cut, text_matches_shot; Кадр 4 — почти чёрный крупный план текстуры кожи без кейса и без текста: выглядит как случайный чёрный кадр/пустая вставка, а не осмысленный переход; В кадре 6 текст «Looks like a mini wallet» наезжает на кейс и частично перекрыт им, нижняя строка «mini wallet» обрезана и плохо читается (анимация появления); Кадры 1–2: первый кадр показывает открытый кейс, но видно только одну конфету (золотая упаковка), а не 2 — «Holds 2» не раскрыто
- проверка: ❌ визуально: text_readable, text_not_cut, text_matches_shot

## Время

- нарезка: 13.1 мин
- рендер: 6.1 мин
- загрузка на Диск: 4.1 мин
- всего: 32.1 мин
- Claude (визуальная проверка): 9 запросов ≈ $0.120
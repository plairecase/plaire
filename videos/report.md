# Шаг 4. Тестовые ролики (TEST_2026-11-28_1211)

seed: `60661` (повторить тот же монтаж: run с этим seed)

## 01_p_studio_to_life_organic
- organic, 7.8 с, 4 планов, цвет cognac, сетка 123 BPM
- fix-03: мир studio_paper 75 %, смен мира 1 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (studio_paper, cognac) → studio_closed (studio_paper, cognac) → street (street_hands, cognac, руки bare) → loop (studio_paper, cognac)
- тексты: «The condom case, redesigned.» → «Eco-leather. Ultra-slim.» → «Made to carry.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: нет
- текст: «The condom case, redesigned.» (`p_hook_05`)
- исходники: -6741131299191009673.MP4, IMG_1440.MOV, IMG_1444.MOV
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.6 dBTP; SFX: click «tap x4.wav» 0.0 с, whoosh «swhoosh.wav» 3.2 с
- попыток: 3 (взята 1-я); луп SSIM: 0.983
- визуально (Claude): ❌ text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, first_frame_explains_product, looks_like_ad; Текст «The condom case, redesigned.» наложен на кейс и перекрывается им (слово «redesigned» заходит на кнопку/клапан); Текст «Eco-leather. Ultra-slim.» перекрывает логотип PLAIRE на коробке, надпись сливается с серебряным тиснением и плохо читается; Белый текст на светлом фоне студии и на светлом небе имеет слабый контраст, особенно «Made to carry.» и первые кадры
- проверка: ❌ визуально: text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, first_frame_explains_product, looks_like_ad

## 02_p_gloves_pov_organic
- organic, 7.8 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → loop (gloves, black, руки gloves)
- тексты: «Your condoms deserve better.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: нет
- текст: «Your condoms deserve better.» (`p_hook_17`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.6 dBTP; SFX: click «click.wav» 0.0 с, magnet «short swoosh x2.wav» 1.9 с
- попыток: 3 (взята 1-я); луп SSIM: 0.863
- визуально (Claude): ❌ text_readable, text_not_cut, text_matches_shot, first_frame_explains_product; Белый текст на светло-сером фоне имеет слабый контраст, особенно в кадре 8 «Looks like a mini wallet», где он почти сливается с фоном; В кадре 1 открытый кейс обрезан краем кадра слева и справа, внутри видна только одна упаковка, а не две; В кадре 3 надпись «Hidden magnetic closure» частично перекрыта пальцами и перчаткой
- проверка: ❌ визуально: text_readable, text_not_cut, text_matches_shot, first_frame_explains_product

## 03_p_gloves_pov_promote
- promote, 9.1 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → card (gloves, black, руки gloves)
- тексты: «Slim enough to forget.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: да
- текст: «Slim enough to forget.» (`p_hook_11`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.6 dBTP; SFX: click «click.wav» 0.0 с, magnet «box slide 1.wav» 1.9 с
- попыток: 3 (взята 1-я); луп SSIM: —
- визуально (Claude): ❌ text_readable, text_not_cut, text_matches_shot; Кадр 1: открытый чехол показывает только один презерватив, а не два, поэтому «Holds 2» не раскрыт; кейс обрезан краями кадра; Верхняя надпись «ULTRA-SLIM CONDOM CASE» микроскопическая и почти не читается на сером фоне; Надпись «Looks like a mini wallet.» в кадре 6 накладывается на светлую перчатку и плохо читается, нижняя строка почти сливается
- проверка: ❌ визуально: text_readable, text_not_cut, text_matches_shot

## Время

- нарезка: 12.0 мин
- рендер: 4.9 мин
- загрузка на Диск: 0.5 мин
- всего: 26.8 мин
- Claude (визуальная проверка): 9 запросов ≈ $0.121
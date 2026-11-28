# Шаг 4. Тестовые ролики (TEST_2026-11-28_1526)

seed: `72379` (повторить тот же монтаж: run с этим seed)

## 01_p_studio_to_life_organic
- organic, 8.1 с, 4 планов, цвет cognac, сетка 89 BPM
- fix-03: мир studio_paper 83 %, смен мира 1 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (studio_paper, cognac) → studio_closed (studio_paper, cognac) → street (street_hands, cognac, руки bare) → loop (studio_paper, cognac)
- тексты: «The condom case, redesigned.» → «Eco-leather. Ultra-slim.» → «Made to carry.»
- проверки: первая склейка 1.33 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.35 с, цена на экране: нет
- текст: «The condom case, redesigned.» (`p_hook_05`)
- исходники: IMG_1440.MOV, IMG_1444.MOV, IMG_8801.MOV
- звук: музыка «ssstik.io_1795780819059», 89 BPM, с 10.6 с; -14.0 LUFS, пик -4.2 dBTP; SFX: click «phone tap 3.wav» 0.0 с, whoosh «short swoosh x2.wav» 2.5 с, whoosh «harsh whoosh 1.wav» 2.4 с
- попыток: 3 (взята 1-я); луп SSIM: 0.996
- визуально (Claude): ❌ text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, first_frame_explains_product, looks_cheap; Заголовок «The condom case, redesigned.» в кадрах 1–2 перекрывается корпусом кейса — текст налезает на продукт и плохо читается; Текст «Eco-leather. Ultra-slim.» в кадре 3 перекрыт чёрной коробкой с логотипом PLAIRE, часть слов нечитаема; В кадре 3 показан закрытый кейс и коробка, а не открытый кейс — текст про эко-кожу не подкреплён видимой деталью, смена ракурса резкая
- проверка: ❌ визуально: text_readable, text_not_cut, shots_feel_continuous, text_matches_shot, first_frame_explains_product, looks_cheap

## 02_p_gloves_pov_organic
- organic, 8.1 с, 5 планов, цвет black, сетка 89 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → loop (gloves, black, руки gloves)
- тексты: «Your condoms deserve better.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.33 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.35 с, цена на экране: нет
- текст: «Your condoms deserve better.» (`p_hook_17`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780819059», 89 BPM, с 10.6 с; -14.0 LUFS, пик -3.8 dBTP; SFX: click «click x2.wav» 0.0 с, magnet «harsh whoosh 1.wav» 2.0 с, whoosh «charge with swoosh.wav» 2.4 с
- попыток: 3 (взята 1-я); луп SSIM: 0.988
- визуально (Claude): ❌ text_not_cut, first_frame_explains_product; Тёмный текст на светло-сером фоне читается, но шрифт тонкий и мелкий, на кадрах 3 и 6 текст частично пересекается с белой перчаткой; Текст «Hidden magnetic closure» в кадре 3 заходит на перчатку справа, край слова «closure» близок к краю кадра; На кадрах 1, 2 и 7–9 открытый кейс обрезан краями кадра по левому и правому краю
- проверка: ❌ визуально: text_not_cut, first_frame_explains_product

## 03_p_gloves_pov_promote
- promote, 9.1 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → card (gloves, black, руки gloves)
- тексты: «Small case. Calm mind.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: да
- текст: «Small case. Calm mind.» (`p_hook_14`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.5 dBTP; SFX: click «shutter clicks 2.wav» 0.0 с, magnet «swoosh 1.wav» 1.9 с, whoosh «soft whoosh 1.wav» 3.1 с
- попыток: 3 (взята 2-я); луп SSIM: —
- визуально (Claude): ❌ text_readable, text_not_cut, case_visible, text_matches_shot; Кадр 4 — почти полностью чёрный (крупный план текстуры кожи), ни кейса, ни текста: выглядит как пропуск или ошибка, а не как переход; В кадре 1 открытый кейс показывает только один презерватив, а не два — «Holds 2» не раскрыт; В кадре 6 текст «Looks like a mini wallet.» перекрыт кейсом и обрезан («mini wallet» уходит под продукт и полупрозрачный)
- проверка: ❌ визуально: text_readable, text_not_cut, case_visible, text_matches_shot

## Время

- нарезка: 16.5 мин
- рендер: 8.2 мин
- загрузка на Диск: 5.9 мин
- всего: 40.4 мин
- Claude (визуальная проверка): 9 запросов ≈ $0.122
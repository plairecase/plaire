# Шаг 4. Тестовые ролики (TEST_2026-11-28_1241)

seed: `62507` (повторить тот же монтаж: run с этим seed)

## 01_p_gloves_pov_organic
- organic, 7.8 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → loop (gloves, black, руки gloves)
- тексты: «The condom case, redesigned.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: нет
- текст: «The condom case, redesigned.» (`p_hook_05`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.6 dBTP; SFX: click «phone tap 1.wav» 0.0 с, magnet «air.wav» 1.9 с
- попыток: 3 (взята 1-я); луп SSIM: 0.863
- визуально (Claude): ❌ text_readable, text_not_cut, text_matches_shot, first_frame_explains_product, looks_like_ad; Кадр 1: кейс обрезан краями кадра, видна только одна застёжка и один презерватив, второй презерватив не показан, поэтому «2 внутри» не читается; Кадр 7: текст «Looks like a mini wallet.» перекрыт верхней гранью кейса, нижняя строка частично срезана; Серый тёмный текст на сером фоне в кадре 8 бледный, контраст слабый
- проверка: ❌ визуально: text_readable, text_not_cut, text_matches_shot, first_frame_explains_product, looks_like_ad

## 02_p_gloves_pov_organic
- organic, 7.8 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → loop (gloves, black, руки gloves)
- тексты: «Looks like a wallet.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: нет
- текст: «Looks like a wallet.» (`p_hook_06`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.6 dBTP; SFX: click «tap.wav» 0.0 с, magnet «box slide 1.wav» 1.9 с
- попыток: 3 (взята 1-я); луп SSIM: 0.863
- визуально (Claude): ❌ text_readable, text_not_cut, text_matches_shot, first_frame_explains_product; Кадр 8: текст «Looks like a mini wallet.» светло-серый на светлом фоне, контраст низкий, читается плохо; Кадр 7: текст «Looks like a mini wallet.» перекрыт кейсом — слово «wallet.» наезжает на верхний край продукта; Кадр 1: в открытом кейсе видна одна обёртка презерватива, а не два, поэтому первый кадр не показывает, что вмещает 2 штуки
- проверка: ❌ визуально: text_readable, text_not_cut, text_matches_shot, first_frame_explains_product

## 03_p_gloves_pov_promote
- promote, 9.1 с, 5 планов, цвет black, сетка 123 BPM
- fix-03: мир gloves 100 %, смен мира 0 ✅ · руки ✅ · цвет ✅ · текст = план ✅ · внутри в первые 3 с ✅
- планы: inside (gloves, black, руки gloves) → close (gloves, black, руки gloves) → profile (gloves, black, руки gloves) → palm (gloves, black, руки gloves) → card (gloves, black, руки gloves)
- тексты: «Small case. Calm mind.» → «Hidden magnetic closure.» → «Ultra-slim.» → «Looks like a mini wallet.»
- проверки: первая склейка 1.47 с, склейки на долях ✅, целые такты ✅, самый длинный план 1.95 с, цена на экране: да
- текст: «Small case. Calm mind.» (`p_hook_14`)
- исходники: IMG_1293.mov, IMG_1393.mov
- звук: музыка «ssstik.io_1795780760321», 123 BPM, с 0.0 с; -14.0 LUFS, пик -5.5 dBTP; SFX: click «tap.wav» 0.0 с, magnet «short swoosh x2.wav» 1.9 с
- попыток: 3 (взята 1-я); луп SSIM: —
- визуально (Claude): ❌ text_readable, text_matches_shot; Первый кадр: открытый кейс показывает только один презерватив в золотой упаковке, а не 2 — не видно, что вмещает 2, и продукт сразу не считывается как кейс; Текст «Looks like a mini wallet.» в 6-м кадре частично серый/полупрозрачный (слово «wallet.» бледнее) — низкий контраст на светлом фоне; Текст «Small case. Calm mind.» повторяется в двух кадрах подряд, а «Looks like a mini wallet.» — в двух кадрах с разным действием; выглядит как затянутый повтор
- проверка: ❌ визуально: text_readable, text_matches_shot

## Время

- нарезка: 18.0 мин
- рендер: 6.3 мин
- загрузка на Диск: 0.2 мин
- всего: 29.8 мин
- Claude (визуальная проверка): 9 запросов ≈ $0.123
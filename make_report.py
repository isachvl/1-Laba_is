"""Четыре страницы отчёта, паспорт и ответы, заполненные реальными замерами."""
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape
import mlflow
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle


def generate(directory):
    directory=Path(directory)
    s=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    m=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
    checks=json.loads((directory/'checks.json').read_text(encoding='utf-8'))
    rows=[json.loads(x) for x in (directory/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    if m['status']!='completed':
        raise ValueError('Эксперименты не завершены')
    output=Path('report'); output.mkdir(exist_ok=True)
    logs={name:(directory/f'server_{name}.log').read_text(encoding='utf-8') for name in ('single','load','half')}
    excerpts={name:'\n'.join(line for line in text.split('model loaded')[0].splitlines() if any(
        key in line for key in ('KV buffer size','n_ctx','n_layer','n_head_kv','n_embd_head','model size','model params','build:')))
        for name,text in logs.items()}
    commands={name:json.loads((directory/f'command_{name}.json').read_text()) for name in logs}
    passport=f'''# Паспорт сервера ЛР1

Модель: Qwen/Qwen3-4B-Instruct-2507 (instruct, поддержка tools через Jinja).
GGUF: {m['model_repo']}, ревизия {m['model_revision']}.
Файл: Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf, Q4_K_M.
SHA-256: {m['model_sha256']}.
Размер файла весов: {m['model_bytes']} байт ({m['model_bytes']/2**30:.3f} ГиБ).
Сервер: llama.cpp b12110, commit cd959bae9, 0.9.0-dev, Windows x86_64 CPU.
Устройство: AMD Ryzen 7 3700X, {m['physical_cores']} физических ядер,
{m['logical_cores']} логических, RAM {m['ram_bytes']/2**30:.2f} ГиБ.
Потоки: 8 для prefill и decode. GPU не используется (-ngl 0).
KV-кеш: K=f16, V=f16, 36 слоёв, 8 KV-голов, размер головы 128.
Расчёт: 2*36*8*128*2 = 147456 байт/токен = 144 КиБ/токен.
Общий контекст 16384: 2304 МиБ KV; 8192: 1152 МиБ.
Лимит слота и фактический буфер проверяются по журналам ниже.
API: http://127.0.0.1:8080/v1; model=qwen3-4b-instruct-2507.
Параметры по умолчанию: endpoint.yaml. Замеры: temperature=0, top_p=1,
top_k=0, min_p=0, repeat_penalty=1, seed=42, ignore_eos=true.
cache_prompt=false в основных опытах, true только в опыте с кешем.
Дополнительный RAM-кеш запросов отключён флагом --cache-ram 0;
повторное использование префикса внутри активного слота сохраняется.
Источник каркаса ЛР0: commit {m['source_lab0_commit']}.
Запуск: {directory}; начало: {m['started']}; окончание: {m['finished']}.
MLflow run: {m['mlflow_run_id']}.
'''
    for name in logs:
        passport+=f'\n## {name}\n\n```powershell\n'+ ' '.join(commands[name])+'\n```\n\n```text\n'+excerpts[name]+'\n```\n'
    (output/'passport.md').write_text(passport,encoding='utf-8')
    r=next(r for r in rows if r['condition']['series']=='output' and r['output_tokens']==64)
    cache=s['cache']; fit=s['fit']; best=s['load_max_clients']; half=s['half_max_clients']
    defense=f'''# Защита лабораторной №1

## Что показать преподавателю
1. report/report.pdf - цель, прогноз, три графика, таблица и вывод.
2. report/passport.md и журналы server_single.log, server_load.log, server_half.log.
3. client.py: t0 перед запросом, t1 и tn по непустым фрагментам; usage для числа токенов.
4. prompts.py: токенизация и chat template самого сервера, проверка длины через usage.
5. results.jsonl, checks.json и warmup.jsonl: прогрев отделён от статистики.
6. MLflow: эксперимент lr1, запуск {m['mlflow_run_id']}, папки raw и analysis.
7. Продемонстрировать demo.py на запущенном сервере; не нужно повторять все опыты при защите.

## 1. Почему TTFT растёт, а TPOT почти не зависит от длины ответа?
Prefill обрабатывает весь вход: больше токенов - больше вычислений, внимание также
зависит от длины. Decode выдаёт по одному токену и на каждом шаге читает веса;
число шагов меняется, стоимость одного шага меняется слабее. При длинном контексте
KV-кеш увеличивается, поэтому TPOT не обязан быть строго постоянным.
Покажите 01_ttft.png и 02_output.png, реальные значения в summary.json.

## 2. Пересчёт TPOT и знаменатель N-1
Реальный запрос {r['id']}: t0={r['t0']:.9f}, t1={r['t1']:.9f}, tn={r['tn']:.9f}, N={r['output_tokens']}.
TTFT=t1-t0={r['ttft_s']:.6f} с.
TPOT=(tn-t1)/(N-1)={r['tpot_s']:.6f} с.
Между первым и последним токеном N-1 интервалов. Число сетевых фрагментов
не равно числу токенов. При N=1 TPOT не определён.
Контрольный пример задания: 0.4 с и (2.4-0.4)/100=0.020 с.

## 3. KV-кеш для 8 пользователей по 4000 токенов
2*36*8*128*2*4000*8 = 4718592000 байт = 4500 МиБ = 4.3945 ГиБ.
Это только входы; ответы добавляют 144 КиБ на каждый токен каждого пользователя.
В 16 ГБ RAM веса Q4_K_M + такой кеш теоретически помещаются, но нужно место ОС
и вычислительным буферам. В текущую конфигурацию сервера НЕ помещаются:
нужно 32000 токенов, а выделено 16384, и настроено только четыре слота.
Наличие памяти компьютера не означает, что она выделена этому серверу.

## 4. Почему throughput растёт, а задержка ухудшается?
При batching чтение весов используется для нескольких запросов, увеличивая
суммарные токены/с. Но шаг батча длиннее, prefill конкурирует с decode, а при
исчерпании слотов запросы ждут. На CPU ускорение не обязано быть линейным:
общая пропускная способность RAM и вычисления ограничены. Покажите таблицу нагрузки.

## 5. Что дали повторные запросы?
TTFT: {', '.join(f'{x:.4f}' for x in cache['ttft_s'])} с.
Первый/второй = {cache['speedup_second']:.2f}, первый/третий = {cache['speedup_third']:.2f}.
Повторное использование KV общего префикса экономит prefill. У агента описания
24 инструментов повторяются: если они стоят в начале и слот сохраняет кеш,
их не надо обрабатывать заново. Уникальная метка в начале мешает этому;
в основных опытах дополнительно задан cache_prompt=false.

## 6. Температура 0, но ответы разные: ошибка?
Нет: temperature=0 выбирает максимум, но не обеспечивает битовую идентичность
вычислений. Разный batching, порядок операций и округление могут изменить
почти равные logits. В нашем тесте два последовательных ответа совпали:
{checks['temperature_0_texts_equal']}. Это результат конкретной проверки, не гарантия.

## 7. Уменьшение контекста вдвое
Прогноз до запуска: для llama.cpp заранее выделенный KV уменьшится вдвое;
16384*144 КиБ = 2304 МиБ, 8192*144 КиБ = 1152 МиБ.
При четырёх слотах лимит каждого уменьшается с 4096 до 2048, но 1152 токена
на запрос всё ещё помещаются. Проверка: server_load.log против server_half.log,
таблицы load_table.csv и half_table.csv. Максимальная прошедшая SLO нагрузка
в проверенной сетке: {best} и {half} соответственно (0 означает ни одной).
Это не универсальный закон для vLLM: там пул KV может определяться свободной
VRAM независимо от max_model_len, и уменьшение длины не обязательно уменьшает пул.

## Что говорить о границе нагрузки
Пределы заданы ДО опытов: p90 TTFT <=30 с, медиана TPOT <=250 мс.
Goodput проверяет оба предела отдельно у каждого запроса.
Проверены только c=1,2,4, по 16 запросов. Если c=4 проходит, найдено «не менее 4»,
а не абсолютный максимум. При c<=4 и четырёх слотах устойчивой очереди из-за
нехватки KV не ожидается: 4*1152=4608 токенов <16384. Рост TTFT сам по себе
не доказывает очередь. Смотрите серверные метрики и журнал, не выдумывайте её.

## Кодогенерация
Код измерителя, сценариев, анализа и отчёта подготовлен с помощью Codex.
Сохранён подход ЛР0 Experiment/Results, YAML, метаданные и MLflow.
Замеры выполнены локально настоящим llama.cpp; значения не сгенерированы.
Перед защитой нужно понимать формулы и уметь найти одну запись и пересчитать её.
'''
    (output/'defense.md').write_text(defense,encoding='utf-8')
    pdfmetrics.registerFont(TTFont('Arial','C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont('ArialBold','C:/Windows/Fonts/arialbd.ttf'))
    styles={
      'body':ParagraphStyle('body',fontName='Arial',fontSize=10,leading=14,spaceAfter=7),
      'h1':ParagraphStyle('h1',fontName='ArialBold',fontSize=16,leading=20,spaceAfter=12),
      'h2':ParagraphStyle('h2',fontName='ArialBold',fontSize=12,leading=16,spaceAfter=8),
      'small':ParagraphStyle('small',fontName='Arial',fontSize=8,leading=10,spaceAfter=5)}
    flow=[]
    def p(text,style='body'): flow.append(Paragraph(escape(text),styles[style]))
    def pic(name): flow.append(Image(str(directory/name),width=170*mm,height=76.6*mm))
    def table(data,widths):
        t=Table([[Paragraph(escape(str(c)),styles['small']) for c in row] for row in data],colWidths=widths)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9edf2')),
                              ('GRID',(0,0),(-1,-1),.4,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),
                              ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        flow.append(t); flow.append(Spacer(1,8))
    p('Лабораторная работа №1','h1')
    p('Инференс и развёртывание языковой модели','h2')
    p('Цель: измерить влияние длины входа, длины ответа и числа клиентов на TTFT, TPOT и пропускную способность собственного OpenAI-совместимого сервера.')
    p('1. Условия и прогноз','h2')
    p(f"CPU-профиль: AMD Ryzen 7 3700X, 8 потоков, RAM {m['ram_bytes']/2**30:.2f} ГиБ. llama.cpp b12110, Qwen3-4B-Instruct-2507 Q4_K_M. GPU отключён. Контекст 16384: один слот в опытах 1-2, четыре в опыте 3. Полный паспорт, команды, хеши и журналы приложены.")
    p('Прогноз записан до запусков: TTFT растёт примерно линейно, на длинном входе возможен более быстрый рост; TPOT ожидается 0.10-0.25 с. При условной полосе RAM 25-40 ГБ/с чтение 2.5 ГБ весов занимает не менее 63-100 мс. Ожидалось нарушение SLO при четырёх клиентах.')
    p('SLO CPU: p90 TTFT ≤ 30 с, медиана TPOT ≤ 250 мс. Это допустимое ожидание для учебной локальной модели, но не комфортный промышленный стандарт. Goodput - число запросов, выполнивших оба индивидуальных предела, за секунду.')
    p('2. Память и методика','h2')
    p(f"FP16: примерно 4 млрд × 2 байта = 8 ГБ весов. Файл Q4_K_M занимает {m['model_bytes']/2**30:.3f} ГиБ; это размер GGUF, не полный RSS процесса. KV хранится в FP16: 2 × 36 × 8 × 128 × 2 = 147456 байт = 144 КиБ/токен. 16384 токена требуют 2304 МиБ, 8192 - 1152 МиБ. Сравнение с фактическим буфером - в паспорте и журналах.")
    p('Данные: Pride and Prejudice, Project Gutenberg №1342; исходный текст и SHA-256 сохранены. Токенизатор сервера формирует точную длину с chat template; метка запроса стоит первой. Temperature=0 и параметры sampling переданы явно, ignore_eos=true, длина проверена по usage. Прогрев каждой серии хранится отдельно. Для основных серий cache_prompt=false; дополнительный RAM-кеш отключён (--cache-ram 0).')
    p(f"Проверки: арифметика 400 мс / 20 мс; запросы дали ровно 64 токена; тексты при temperature=0 совпали: {checks['temperature_0_texts_equal']}. Results сохраняет t0, t1, tn, все времена фрагментов, usage, finish_reason и статус. Сводки вычислены из JSONL, артефакты загружены в MLflow.")
    flow.append(PageBreak())
    p('3. Опыт 1: длина входа и TTFT','h1')
    pic('01_ttft.png')
    table([['Вход','Медиана TTFT, с','Диапазон, с','Вход / TTFT, ток/с']]+[
        [g['level'],f"{g['ttft_median']:.3f}",f"{g['ttft_min']:.3f}-{g['ttft_max']:.3f}",f"{g['prefill_tokens_s_proxy']:.1f}"] for g in s['input']],
        [25*mm,45*mm,50*mm,50*mm])
    p('По пять последовательных запросов каждой длины, ответ 16 токенов. Вход/TTFT - клиентская оценка скорости prefill: она включает HTTP и первый шаг decode, поэтому не равна чистому серверному throughput prefill.')
    ratio=s['input'][-1]['ttft_median']/s['input'][0]['ttft_median']
    p(f"При увеличении входа с 128 до 4096 токенов (32 раза) медиана TTFT изменилась в {ratio:.2f} раза. Скорость не постоянна: она снизилась с {s['input'][0]['prefill_tokens_s_proxy']:.1f} до {s['input'][-1]['prefill_tokens_s_proxy']:.1f} токена/с. На длинном входе возрастает стоимость внимания и обращения к KV; фиксированные накладные расходы и батчи prefill также влияют на зависимость.")
    p('Проверка кеширования префикса','h2')
    p(f"Один запрос на 2048 токенов отправлен трижды с cache_prompt=true. TTFT: {', '.join(f'{x:.4f}' for x in cache['ttft_s'])} с. Отношение первого ко второму: {cache['speedup_second']:.2f}; к третьему: {cache['speedup_third']:.2f}. Прогрев использовал другой запрос. Повторный общий префикс позволяет повторно использовать KV и сократить обработку входа.")
    p('Для агента с 24 инструментами это экономит обработку повторяющихся описаний, если они находятся в общем префиксе. Для измерения зависимости от длины такой эффект искажает TTFT, поэтому в основной серии кеш отключён.')
    flow.append(PageBreak())
    p('4. Опыт 2: длина ответа','h1')
    pic('02_output.png')
    table([['Ответ, токены','Медиана полного времени, с','Медиана TPOT, мс']]+[
        [g['level'],f"{g['e2e_median']:.3f}",f"{g['tpot_median']*1000:.2f}"] for g in s['output']],
        [40*mm,70*mm,60*mm])
    p(f"Вход 1024 токена, по пять повторов. МНК по всем 20 запросам: T(N)={fit['intercept_s']:.4f}+{fit['slope_s']:.6f}N с; R²={fit['r2']:.4f}. Медиана TTFT={fit['ttft_median']:.4f} с, медиана TPOT={fit['tpot_median']*1000:.2f} мс.")
    p('В модели T=TTFT+(N-1)·TPOT коэффициент при N близок к TPOT, а свободный член - к TTFT-TPOT. Разница с наблюдаемыми медианами возможна из-за роста KV по мере генерации и изменения производительности CPU. Линейная аппроксимация описывает тенденцию, не заменяет сырые измерения.')
    p(f"Граница 8/300≈0.027 с из задания относится к T4 и FP16. Здесь другой процессор, формат весов и полоса памяти. Измеренный TPOT {fit['tpot_median']:.4f} с нельзя сравнивать с 27 мс как с аппаратной границей данного CPU; дополнительные расходы создают деквантование, чтение KV и вычисления.")
    p('Пример пересчёта из сырых отметок','h2')
    p(f"N={r['output_tokens']}; t1-t0={r['ttft_s']:.6f} с; tn-t1={r['tn']-r['t1']:.6f} с. TPOT=(tn-t1)/63={r['tpot_s']:.6f} с. Между 64 токенами 63 интервала. Число сетевых фрагментов вместо usage использовать нельзя.")
    flow.append(PageBreak())
    p('5. Опыт 3: нагрузка и выводы','h1')
    pic('03_load.png')
    table([['c','ток/с','запр/с','TTFT med/p90, с','TPOT, мс','goodput','SLO']]+[
        [g['level'],f"{g['output_tokens_s']:.2f}",f"{g['requests_s']:.3f}",f"{g['ttft_median']:.2f}/{g['ttft_p90']:.2f}",f"{g['tpot_median']*1000:.1f}",f"{g['goodput']:.3f}",'да' if g['slo_pass'] else 'нет'] for g in s['load']],
        [10*mm,21*mm,22*mm,46*mm,25*mm,26*mm,20*mm])
    p('На каждом уровне 16 запросов, вход 1024, выход 128; разные фрагменты книги. Клиенты работают в замкнутом цикле: следующий запрос сразу после ответа. Throughput рассчитан по времени от первой отправки до последнего полученного ответа; подготовка запросов и прогрев исключены. Метрики сервера до/после сохранены.')
    p(f"Наибольшее c, выполнившее оба SLO в сетке 1,2,4: {best} (0 - ни одного). " + ('При c=4 верхняя граница не найдена: доказана поддержка не менее четырёх клиентов.' if best==4 else 'Вывод относится к проверенным уровням и этому компьютеру.'))
    p('KV теоретически вмещает floor(16384/1152)=14 таких последовательностей, но сервер ограничен четырьмя слотами. Четыре запроса занимают 4608 токенов; нехватка KV не ожидается. Рост задержки нельзя автоматически считать очередью: CPU делит вычисления и память. Снимки до/после не измеряют максимум очереди внутри уровня.')
    p(f"Проверка уменьшенного контекста: KV 2304→1152 МиБ, лимит одного слота 4096→2048. Все входы+ответы по 1152 токенов помещаются. Максимальное прошедшее c стало {half}; подробная таблица half_table.csv. Один прогон не отделяет небольшой эффект от фоновой нагрузки.")
    p('Для ЛР2-ЛР8: длинные RAG-документы и описания инструментов увеличат ожидание первого токена; общие префиксы стоит кешировать. Увеличение числа пользователей требует проверки SLO, а не только токенов/с. Контекст и slots необходимо выбирать под размер будущих запросов.')
    p('Кодогенерация: Codex помог подготовить адаптер каркаса ЛР0, генератор, анализ и отчёт. Все числа получены реальным локальным запуском. Источники: методичка ЛР1; github.com/isachvl/1Laba_is; ggml-org/llama.cpp (server README); модель bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF; gutenberg.org/ebooks/1342. Полные идентификаторы и SHA-256 - в паспорте и манифесте.','small')
    def footer(canvas,doc):
        canvas.setFont('Arial',8); canvas.setFillColor(colors.grey)
        canvas.drawString(20*mm,12*mm,'ЛР1 · Инференс и развёртывание языковой модели')
        canvas.drawRightString(190*mm,12*mm,str(doc.page))
    SimpleDocTemplate(str(output/'report.pdf'),pagesize=(210*mm,297*mm),
                      rightMargin=20*mm,leftMargin=20*mm,topMargin=18*mm,bottomMargin=20*mm,
                      title='Лабораторная работа №1').build(flow,onFirstPage=footer,onLaterPages=footer)
    mlflow.set_tracking_uri('sqlite:///mlflow.db')
    with mlflow.start_run(run_id=m['mlflow_run_id']):
        mlflow.log_artifacts(str(output),artifact_path='report')


if __name__=='__main__':
    generate(Path('latest_run.txt').read_text(encoding='utf-8').strip())

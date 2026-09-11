# Spark на Kubernetes и S3 — редакция для собеседования

Статус: подготовлено к оценке владельцем. Скиллы не изменены; перенос правил в скилл разрешён только после явного одобрения качества пула.

## Содержание и подача

Исходные 108 карточек пересобраны в 45 вопросов. Убраны повторы, искусственные микрошаги и отдельный раздел про Spark UI и наблюдение. Вопросы проверяют знание механизмов и понимание их границ; новые механизмы раскрываются до вопросов, которые на них опираются.

- Пять областей, десять смысловых подкатегорий.
- Вертикальные уровни: **base → junior → middle → senior**.
- Заголовки и плашки тем без нумерации.
- В ответах: главная мысль, выделения, сравнения, последовательности, схемы и примеры кода с пояснением результата.
- 14 блоков Python/PySpark; остальные блоки — текстовые схемы и явно обозначенный псевдокод.
- Число вопросов не подгоняется под одинаковое заполнение всех ячеек.

## Как проходить

Области слева направо: выполнение Spark → S3 → Kubernetes → ресурсы → корректность. В каждой области сначала пройти левую подкатегорию сверху вниз, затем правую. Уровни описывают глубину внутри подкатегории, а не предлагают читать всю доску горизонтально.

Для старта достаточно понимать строки, столбцы и простые операции над таблицами. `spark` в примерах — созданная SparkSession. Примеры обращения к S3 предполагают подготовленную среду и права. Псевдокод транзакции приёмника не является готовым API Spark.

| Уровень | Что проверяет |
|---|---|
| base | Понятия, роли и различия базовых сущностей |
| junior | Устройство механизма и базовое применение |
| middle | Взаимодействие механизмов, ограничения и последствия выбора |
| senior | Обоснование компромиссов и гарантий при проектировании |

## Состав пула

### Выполнение Spark

**Модель выполнения**

- **base** · [DataFrame и распределённая таблица](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-01.md) — Что представляет собой DataFrame в Spark и чем он отличается от таблицы, целиком загруженной в память одного процесса?
- **base** · [Роли driver и executors](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-03.md) — Как распределены обязанности процессов Spark-приложения и проходит ли весь обрабатываемый набор через управляющий процесс?
- **junior** · [Ленивое выполнение и оптимизация плана](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-04.md) — Чем трансформации (transformations) DataFrame отличаются от действий (actions)? Как ленивое выполнение позволяет оптимизировать запрос?
- **junior** · [Партиции, tasks, stages и jobs](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-05.md) — Как связаны партиция данных, отдельная задача и этап вычисления в Spark? Почему число задач не равно числу executors?
- **junior** · [DAG и границы обмена данными](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-06.md) — Чем узкие трансформации (narrow transformations) отличаются от широких (wide transformations)? Как это связано с зависимостями партиций и границами stages?
- **middle** · [Сохранение промежуточных результатов](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-07.md) — Когда сохранение промежуточного DataFrame ускоряет повторные вычисления, а когда только расходует ресурсы?

**Обмен и операции по ключу**

- **junior** · [Частичная и окончательная агрегация](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-12.md) — Как Spark вычисляет общую сумму и среднее по ключу, если исходные строки находятся в разных партициях?
- **junior** · [Устройство распределённого join](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-14.md) — Как Spark соединяет две распределённые таблицы по общему ключу?
- **middle** · [Broadcast join и границы его применимости](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-15.md) — При каких условиях раздача меньшей таблицы всем executors выгоднее shuffle join? Какие ограничения памяти нужно учитывать?
- **middle** · [Skew и неделимая работа по ключу](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-16.md) — Почему неравномерное распределение ключей по-разному влияет на агрегацию и соединение таблиц?
- **senior** · [Адаптивное выполнение запросов](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-18.md) — Какие решения физического плана можно пересмотреть после получения фактических размеров данных? Какую работу такая адаптация уже не может устранить?
- **senior** · [Salting и сохранение смысла вычисления](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-19.md) — Как разделить горячий ключ между задачами для агрегации и inner join? Обоснуйте, какие дополнительные действия сохраняют исходный результат.

### Хранение в S3

**Объектное хранение**

- **base** · [Объекты, ключи и префиксы S3](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-01.md) — Как данные организованы в S3 и чем такое хранение отличается от файловой системы на диске?
- **junior** · [Доступ Spark к объектам через S3A](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-03.md) — Как Spark читает и записывает объекты S3, если его код обращается к путям, похожим на файловые?
- **junior** · [Обнаружение объектов и чтение данных](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-04.md) — Из каких частей складывается чтение распределённого набора файлов из S3?
- **middle** · [Согласованность объекта и целого набора](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-06.md) — Какие гарантии видимости даёт S3 после записи объекта и распространяются ли они на набор файлов одной таблицы?
- **middle** · [Переименование в объектном хранилище](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-07.md) — Почему переименование пути через S3A отличается по стоимости и атомарности от переименования каталога в файловой системе?

**Файлы и таблицы**

- **base** · [Parquet и выборочное чтение](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-09.md) — Как внутреннее устройство Parquet позволяет читать только часть столбцов и строк файла?
- **junior** · [Разбиение хранения и вычислительные партиции](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-12.md) — Чем разбиение файлов по значениям столбца отличается от партиций вычисления и как оно сокращает чтение?
- **middle** · [Размер файлов и гранулярность хранения](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-15.md) — Какие компромиссы определяют количество и размер файлов распределённого датасета?
- **senior** · [Формат файла и формат таблицы](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-18.md) — Когда для общей таблицы достаточно Parquet-файлов, а когда необходим протокол управления версиями? Какие дополнительные обязанности он создаёт?

### Spark на Kubernetes

**Среда и запуск**

- **base** · [Образ, контейнер и воспроизводимость среды](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-01.md) — Что необходимо перенести вместе с кодом Spark-приложения, чтобы оно могло выполняться на разных машинах?
- **base** · [Pod и размещение процессов](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-02.md) — Как Kubernetes превращает описание контейнеров в работающие процессы и выбирает для них машины?
- **junior** · [Запуск Spark и распределение ответственности](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-03.md) — Как распределены обязанности spark-submit, driver и Kubernetes при запуске Spark-приложения?
- **middle** · [Среда driver и среда executors](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-05.md) — Почему наличие зависимости на driver не гарантирует её доступность коду, который выполняют executors?
- **senior** · [Оркестрация и жизненный цикл приложения](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-09.md) — Как разделить ответственность Spark, Kubernetes и системы запуска, чтобы повтор приложения имел однозначный смысл и не порождался несколькими контроллерами независимо?

**Сеть и полномочия**

- **junior** · [Сетевые связи распределённого приложения](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-06.md) — Какие сетевые связи необходимы Spark-приложению на Kubernetes и почему одного доступа к Kubernetes API недостаточно?
- **middle** · [Идентичность и два контура полномочий](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-13.md) — Как разделяются права Spark-приложения на ресурсы Kubernetes и на данные в S3?

### Ресурсы и масштабирование

**Память и промежуточные данные**

- **base** · [Рабочие данные и потребность в памяти](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-01.md) — От чего зависит объём памяти, необходимый executor, и почему его нельзя определить по размеру входных файлов?
- **junior** · [Heap и память контейнера](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-02.md) — Как память, используемая разными частями executor, соотносится с общим бюджетом его контейнера?
- **junior** · [Параллельные tasks и общий бюджет](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-03.md) — Как число одновременно работающих tasks влияет на CPU и память одного executor?
- **middle** · [Spill, shuffle и промежуточное хранилище](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-04.md) — Как Spark обрабатывает промежуточные данные, которые не помещаются в рабочую память, и зачем ему диск при хранении исходных данных в S3?

**Ресурсы и эластичность**

- **junior** · [Requests, limits и размещение ресурсов](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-11.md) — Как Kubernetes учитывает заявленные CPU и память и чем эти значения отличаются от фактического потребления?
- **middle** · [Два уровня эластичности](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-14.md) — Как Spark меняет количество executors и почему это не равнозначно изменению числа узлов Kubernetes?
- **middle** · [Пределы параллельного ускорения](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-17.md) — Какие свойства распределённого вычисления ограничивают ускорение при добавлении executors?
- **senior** · [Размер executors и стоимость вычисления](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-18.md) — Как выбрать между большим числом небольших executors и малым числом крупных? Сопоставьте память, размещение, обмен данными и последствия отказа.

### Корректность и восстановление

**Запись и публикация**

- **base** · [Вычисление и публикация результата](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-01.md) — Что означает готовность распределённого результата для читателя, если разные tasks записывают разные файлы?
- **junior** · [Повторы вычисления и границы отказа](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-03.md) — Как Spark восстанавливает вычисление при потере executor и какие последствия имеет повтор для внешних записей?
- **middle** · [Идемпотентность и воспроизводимость](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-02.md) — Что делает повторный запуск безопасным для результата и чем это отличается от воспроизводимости вычисления?
- **middle** · [Согласование файлов успешных попыток](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-04.md) — Как распределённая запись выбирает результаты успешных попыток tasks и почему устройство S3 влияет на этот процесс?
- **senior** · [Версии, конкурентная публикация и чтение](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-06.md) — Как организовать публикацию новой версии набора файлов при конкурентных writers и длительных чтениях? Какие гарантии нужны при переключении и очистке версий?

**Поток и состояние**

- **base** · [Поток как последовательность вычислений](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-11.md) — Как Spark обрабатывает непрерывно поступающие данные, если у входного набора нет момента окончательного завершения?
- **junior** · [Checkpoint и восстановление потока](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-14.md) — Какие сведения нужно сохранить между запусками потокового запроса, чтобы продолжить его обработку после потери процессов?
- **middle** · [Поздние события и граница состояния](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-16.md) — Как ограничить объём состояния потокового расчёта, если события могут приходить позже времени, к которому относятся?
- **senior** · [Гарантии результата при повторе микропартии](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-18.md) — Как обеспечить один логический эффект микропартии при повторном выполнении? Где должны проходить границы атомарности между прогрессом запроса и приёмником?

## Технические границы

Основа — Spark 3.5.x, PySpark и Amazon S3 general purpose buckets. Версионные особенности сверены с официальными источниками; ссылки стоят в соответствующих ответах. Версия Hadoop в ссылке описывает источник, а не универсальное требование к каждому дистрибутиву Spark.

В исходном локальном паке `spark-s3-kubernetes` сохранены id 45 переработанных тем. 63 избыточные карточки убраны из файлового пула; sync скрывает их seed-записи, сохраняя БД и чек-листы. Полная исходная копия: `/private/tmp/ladder-theory-review/original/`. В локальном контейнере также существует другая доска `spark-k8s-s3`; она не изменена.

## Проверка редакции

- Импорт всех пулов: 0 ошибок; целевой пул — 45 карточек.
- Backend: 145 тестов прошли.
- Smoke: прошёл на свежей временной БД.
- Браузер: проверены 10 подкатегорий, четыре уровня, порядок карточек, жирный текст, таблицы и подсвеченный код.
- Python-примеры проверены синтаксически; исполнение PySpark на реальном Spark-кластере не выполнялось.
- Локальный сервер `:8000`: карточки сверены с файлами; остальные семь пулов и чек-лист не изменились.

[Открыть рабочую доску](http://localhost:8000/#/board/spark-s3-kubernetes).

## Аудит терминологии — 11 сентября 2026

Проверены и отредактированы все 45 карточек. Не каждая содержала фактическую ошибку: часть изменений — явное определение терминов, расшифровка сокращений и привязка к источникам. Состав пула, id, заголовки, уровни, темы и подкатегории сохранены.

Источники ниже подобраны и проверены при этой ревизии. Это не восстановленная история происхождения исходных вопросов: прежние формулировки были авторским обобщением без такой привязки. Примеры и объяснения остаются адаптацией для самоподготовки.

| Карточка | Что исправлено | Источник для сверки |
|---|---|---|
| [DataFrame и распределённая таблица](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-01.md) | Выделены DataFrame, schema, partition и SparkSession; определение схемы перенесено к первому упоминанию. | [Spark: DataFrames](https://spark.apache.org/docs/3.5.7/sql-programming-guide.html#datasets-and-dataframes) |
| [Роли driver и executors](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-03.md) | Явно сопоставлены driver и executors; сохранено различие процессов и машин. | [Spark: роли процессов](https://spark.apache.org/docs/3.5.7/cluster-overview.html) |
| [Ленивое выполнение и оптимизация плана](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-04.md) | Введены transformations/actions, lazy evaluation и Catalyst; убрана смесь «преобразования / actions». | [Статья авторов Spark SQL: Catalyst, §4](https://people.csail.mit.edu/matei/papers/2015/sigmod_spark_sql.pdf) |
| [Партиции, tasks, stages и jobs](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-05.md) | Сопоставлены partition/task/stage/job; убрана преждевременная «узкая цепочка». | [Spark: glossary](https://spark.apache.org/docs/3.5.7/cluster-overview.html#glossary) |
| [DAG и границы обмена данными](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-06.md) | Исправлен критерий narrow dependency; введены narrow/wide transformations, DAG, RDD и lineage; обозначена граница применимости к DataFrame. | [статья авторов Spark об RDD, §4, рис. 4 и §5.1](https://www.usenix.org/system/files/conference/nsdi12/nsdi12-final138.pdf); [Spark: shuffle](https://spark.apache.org/docs/3.5.7/rdd-programming-guide.html#shuffle-operations) |
| [Сохранение промежуточных результатов](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-07.md) | Разведены caching, persistence, materialization и storage level; указан default именно PySpark DataFrame 3.5.7. | [PySpark: DataFrame.cache](https://spark.apache.org/docs/3.5.7/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.cache.html) |
| [Частичная и окончательная агрегация](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-12.md) | Названы partial/final aggregation; устройство среднего сверено с буфером sum/count в исходниках Spark. | [Spark: агрегат Average, буфер sum/count](https://github.com/apache/spark/blob/v3.5.7/sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/expressions/aggregate/Average.scala) |
| [Устройство распределённого join](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-14.md) | Разведены equi-join, shuffle join, sort-merge join и shuffled hash join; определена build side. | [Spark: выбор алгоритмов join](https://github.com/apache/spark/blob/v3.5.7/sql/core/src/main/scala/org/apache/spark/sql/execution/SparkStrategies.scala) |
| [Broadcast join и границы его применимости](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-15.md) | Broadcast hash join сопоставлен с shuffled hash join по объёму build side. | [Spark: подсказки стратегий join](https://spark.apache.org/docs/3.5.7/sql-performance-tuning.html#join-strategy-hints-for-sql-queries) |
| [Skew и неделимая работа по ключу](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-16.md) | Введены data skew и hot key; перекос данных отделён от стоимости работы. | [Spark: перекос join](https://spark.apache.org/docs/3.5.7/sql-performance-tuning.html#optimizing-skew-join) |
| [Адаптивное выполнение запросов](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-18.md) | AQE раскрыт при первом употреблении; адаптивное объединение shuffle-партиций отделено от вызова coalesce(). | [Spark 3.5.7: AQE](https://spark.apache.org/docs/3.5.7/sql-performance-tuning.html#adaptive-query-execution) |
| [Salting и сохранение смысла вычисления](../../content/spark-s3-kubernetes/execution/spark-s3-kubernetes-execution-19.md) | Определены salting и salt; пример обозначен авторским, ссылка на groupBy подтверждает API, а не доказательство алгоритма. | [Spark: groupBy](https://spark.apache.org/docs/3.5.7/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.groupBy.html) |
| [Вычисление и публикация результата](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-01.md) | Явно определены публикация и атомарность набора данных. | [Iceberg: атомарная публикация](https://iceberg.apache.org/docs/latest/reliability/) |
| [Идемпотентность и воспроизводимость](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-02.md) | Введены idempotency, reproducibility и deterministic transformations; раскрыты append / upsert. | [AWS Builders’ Library: идемпотентные повторы](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) |
| [Повторы вычисления и границы отказа](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-03.md) | Разведены task attempt, retry, speculative execution и side effect. | [Spark: retries и speculation](https://spark.apache.org/docs/3.5.7/configuration.html#scheduling) |
| [Согласование файлов успешных попыток](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-04.md) | Разведены commit protocol и output committer; определён multipart upload. | [Hadoop 3.3.4: S3A committers](https://hadoop.apache.org/docs/r3.3.4/hadoop-aws/tools/hadoop-aws/committers.html) |
| [Версии, конкурентная публикация и чтение](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-06.md) | Введены optimistic concurrency control и CAS. | [Iceberg: надёжность обновлений](https://iceberg.apache.org/docs/latest/reliability/) |
| [Поток как последовательность вычислений](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-11.md) | Определены micro-batch, source, sink, offset, state, stateful/stateless; state объяснён до схемы. | [Spark: модель потока](https://spark.apache.org/docs/3.5.7/structured-streaming-programming-guide.html#basic-concepts) |
| [Checkpoint и восстановление потока](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-14.md) | Разведены checkpoint и state store; сохранена граница с содержимым событий и памятью JVM. | [Spark: восстановление через checkpoint](https://spark.apache.org/docs/3.5.7/structured-streaming-programming-guide.html#recovering-from-failures-with-checkpointing) |
| [Поздние события и граница состояния](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-16.md) | Введены event time / processing time / watermark; добавлено ограничение очистки состояния в complete mode. | [Spark 3.5.7: семантика watermark](https://spark.apache.org/docs/3.5.7/structured-streaming-programming-guide.html#semantic-guarantees-of-aggregation-with-watermarking) |
| [Гарантии результата при повторе микропартии](../../content/spark-s3-kubernetes/reliability/spark-s3-kubernetes-reliability-18.md) | At-least-once и exactly-once названы до протокола; явно указаны гарантии foreachBatch по умолчанию. | [Spark: foreachBatch](https://spark.apache.org/docs/3.5.7/structured-streaming-programming-guide.html#foreachbatch) |
| [Рабочие данные и потребность в памяти](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-01.md) | Названо рабочее состояние операции; execution memory отделена от storage memory. | [Spark: управление памятью](https://spark.apache.org/docs/3.5.7/tuning.html#memory-management-overview) |
| [Heap и память контейнера](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-02.md) | Разведены JVM heap, общая память вне heap, управляемый Spark off-heap и memory overhead; названы OutOfMemoryError / OOMKilled. | [Spark 3.5.7: параметры памяти](https://spark.apache.org/docs/3.5.7/configuration.html#application-properties) |
| [Параллельные tasks и общий бюджет](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-03.md) | Определён task slot; сохранено различие Spark-параллелизма и физических CPU. | [Spark: параметры исполнения](https://spark.apache.org/docs/3.5.7/configuration.html#execution-behavior) |
| [Spill, shuffle и промежуточное хранилище](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-04.md) | Разведены spill и shuffle; определены I/O, emptyDir и tmpfs. | [Spark: локальное хранилище на Kubernetes](https://spark.apache.org/docs/3.5.7/running-on-kubernetes.html#local-storage) |
| [Requests, limits и размещение ресурсов](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-11.md) | Разведены request и limit; объяснён CPU throttling. | [Kubernetes: ресурсы контейнеров](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) |
| [Два уровня эластичности](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-14.md) | Разведены dynamic resource allocation и node autoscaling; определён shuffle tracking. | [Spark 3.5.7: dynamic allocation](https://spark.apache.org/docs/3.5.7/job-scheduling.html#dynamic-resource-allocation) |
| [Пределы параллельного ускорения](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-17.md) | Назван закон Амдала; указаны фиксированный объём работы и отсутствие накладных расходов в модели. | [Джин Амдал, 1967: исходная статья](https://www.cs.cmu.edu/~18742/papers/Amdahl1967.pdf) |
| [Размер executors и стоимость вычисления](../../content/spark-s3-kubernetes/resources/spark-s3-kubernetes-resources-18.md) | Расшифрована GC; определение встроено без перегрузки предложения. | [Spark: GC и расход памяти](https://spark.apache.org/docs/3.5.7/tuning.html#garbage-collection-tuning) |
| [Образ, контейнер и воспроизводимость среды](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-01.md) | Явно определены image, container, digest и tag. | [Kubernetes: images, tags и digests](https://kubernetes.io/docs/concepts/containers/images/) |
| [Pod и размещение процессов](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-02.md) | Выделены роли Pod, Node, scheduler, kubelet, container runtime и Namespace. | [Kubernetes: компоненты](https://kubernetes.io/docs/concepts/overview/components/) |
| [Запуск Spark и распределение ответственности](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-03.md) | Cluster mode и client mode определены в соответствующих объяснениях. | [Spark 3.5.7: выполнение на Kubernetes](https://spark.apache.org/docs/3.5.7/running-on-kubernetes.html#how-it-works) |
| [Среда driver и среда executors](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-05.md) | UDF расшифрована до примера; Python worker определён как отдельный процесс. | [PySpark: доставка Python-зависимостей](https://spark.apache.org/docs/3.5.7/api/python/user_guide/python_packaging.html) |
| [Сетевые связи распределённого приложения](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-06.md) | Разведены Service, DNS и NetworkPolicy; указана зависимость политик от сетевого плагина. | [Spark: сетевая доступность driver](https://spark.apache.org/docs/3.5.7/running-on-kubernetes.html#client-mode-networking) |
| [Оркестрация и жизненный цикл приложения](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-09.md) | Введены orchestrator, Operator и reconciliation loop; убрана ссылка на ещё не разобранную идемпотентность. | [Kubernetes: Operator pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/) |
| [Идентичность и два контура полномочий](../../content/spark-s3-kubernetes/runtime/spark-s3-kubernetes-runtime-13.md) | ServiceAccount, RBAC, IAM, KMS, workload identity и credentials раскрыты; IRSA дан как конкретный пример EKS. | [AWS EKS: IAM roles for service accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html); [Kubernetes: ServiceAccount](https://kubernetes.io/docs/concepts/security/service-accounts/) |
| [Объекты, ключи и префиксы S3](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-01.md) | Объект, бакет, ключ и префикс даны явно; замена объекта отделена от включённого S3 Versioning. | [AWS: объекты, бакеты и ключи](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) |
| [Доступ Spark к объектам через S3A](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-03.md) | Выделены S3A и Hadoop FileSystem; сохранено объяснение JVM-зависимостей. | [Hadoop 3.3.4: совместимость S3A](https://hadoop.apache.org/docs/r3.3.4/hadoop-aws/tools/hadoop-aws/troubleshooting_s3a.html); [Hadoop: S3A](https://hadoop.apache.org/docs/r3.3.4/hadoop-aws/tools/hadoop-aws/index.html) |
| [Обнаружение объектов и чтение данных](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-04.md) | Разведены listing и scan; учтён выбор состава файлов через метаданные таблицы. | [Spark: перечисление входных путей](https://spark.apache.org/docs/3.5.7/tuning.html#parallel-listing-on-input-paths) |
| [Согласованность объекта и целого набора](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-06.md) | Разведены strong consistency и atomicity; уточнено поведение при конкурентной записи того же ключа. | [AWS: модель согласованности S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel) |
| [Переименование в объектном хранилище](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-07.md) | Явно названы rename и copy/delete; сохранена граница атомарности одного объекта. | [Hadoop: S3A rename](https://hadoop.apache.org/docs/r3.3.4/hadoop-aws/tools/hadoop-aws/index.html) |
| [Parquet и выборочное чтение](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-09.md) | Разведены row group / column chunk / page и column pruning / predicate pushdown / row group pruning. | [Parquet: устройство файла](https://parquet.apache.org/docs/file-format/); [Spark: поддержка фильтров Parquet](https://spark.apache.org/docs/3.5.7/sql-data-sources-parquet.html#configuration) |
| [Разбиение хранения и вычислительные партиции](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-12.md) | Сопоставлены storage partitioning и Spark partitions; явно определён partition pruning. | [Spark: partition discovery](https://spark.apache.org/docs/3.5.7/sql-data-sources-parquet.html#partition-discovery) |
| [Размер файлов и гранулярность хранения](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-15.md) | Введены small files problem и compaction. | [Iceberg: rewrite_data_files](https://iceberg.apache.org/docs/latest/spark-procedures/#rewrite_data_files) |
| [Формат файла и формат таблицы](../../content/spark-s3-kubernetes/storage/spark-s3-kubernetes-storage-18.md) | Разведены file format / table format, snapshot и catalog. | [Iceberg: метаданные и snapshots](https://iceberg.apache.org/spec/) |

Предыдущая редакция сохранена в `/private/tmp/ladder-theory-review/before-terminology/`. Проверка этой редакции: импорт восьми пулов — 0 ошибок; pytest — 145 passed; полный smoke на свежей БД — passed. Браузер подтвердил совпадение всех 45 карточек с файлами, порядок, 10 подкатегорий, четыре уровня и отображение терминов, таблицы и источника в карточке DAG. Локальная доска :8000 синхронизирована; остальные семь пулов и чек-лист не изменились. 14 Python-примеров проходят синтаксический разбор; на Spark-кластере они не исполнялись. Скиллы остаются без изменений до явного одобрения пула.

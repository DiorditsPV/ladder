---
block: k8s
difficulty: advanced
id: spark-k8s-s3-k8s-07
kind: question
subblock: resources
tags:
- deployment
- monitoring
title: Экзекьюторы висят в Pending
topic: executors-pending
weight: 1
---

## Вопрос
Почему поды экзекьюторов могут висеть в Pending и как найти причину?

## Ответ
Pending значит, что планировщик Kubernetes не нашёл для пода подходящую ноду. Причину он пишет в события: `kubectl describe pod <exec-pod>`, раздел Events, сообщение `FailedScheduling`.

**`Insufficient cpu` или `Insufficient memory`.** Под не помещается ни на одну ноду. Сравнивай не `spark.executor.memory`, а итоговые Requests пода из того же `describe` — с overhead они заметно больше heap — и не с размером ноды, а со свободным на ней местом: часть ресурсов ноды занята системой и служебными подами. Помогает экзекьютор поменьше: меньше ядер и памяти на под, больше подов.

**`didn't match Pod's node affinity/selector` или сообщение про taint.** `nodeSelector` указывает на метку, которой нет ни у одной ноды, или ноды для Spark помечены taint, а в поде нет toleration. Проверь, что эти поля реально попали в под (`kubectl get pod -o yaml`): tolerations и affinity из SparkApplication дописывает вебхук оператора.

**Под ждёт том.** Если локальный каталог вынесен на PVC, том мог не создаться или не привязаться — смотри события PVC.

Отдельный случай — подов экзекьюторов нет вообще, а в логе драйвера `exceeded quota`: квота namespace не дала создать под. Поможет только меньше экзекьюторов или разговор с владельцами кластера.

Джоб при этом не падает: Spark ждёт ресурсы и пишет в лог `Initial job has not accepted any resources`.

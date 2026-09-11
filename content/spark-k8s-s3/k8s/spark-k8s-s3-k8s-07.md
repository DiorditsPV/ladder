---
block: k8s
difficulty: debug
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
Джоб запросил 20 экзекьюторов: драйвер работает, а все поды экзекьюторов висят в Pending, в Spark UI нет ни одного экзекьютора. Как найдёшь причину и что поправишь в своём манифесте?

## Ответ
Pending — планировщик Kubernetes не нашёл для пода ноду. Причину он пишет в события: `kubectl describe pod <exec-pod>`, раздел Events, `FailedScheduling`.

**`Insufficient cpu` или `Insufficient memory`.** Под не влезает ни в одну ноду. Сравнивай не `spark.executor.memory`, а итоговые Requests пода из того же `describe` — с overhead они заметно больше heap — и не с размером ноды, а со свободным на ней: allocatable меньше ёмкости, часть ещё занята DaemonSet-подами. Лечится экзекьютором поменьше: меньше ядер и памяти на под, больше подов.

**`didn't match Pod's node affinity/selector` или сообщение про taint.** Твой `nodeSelector` указывает на метку, которой нет ни у одной ноды, или ноды пула под Spark с taint, а в поде нет toleration. Проверь, что поля реально попали в под (`kubectl get pod -o yaml`): tolerations и affinity из SparkApplication дописывает вебхук оператора.

**Под ждёт том.** Если локальный каталог на PVC по требованию, том мог не создаться или не привязаться — смотри события PVC.

Отдельный случай — подов нет вообще, а в логе драйвера `exceeded quota`: ResourceQuota namespace не дала создать под, и драйвер пробует снова. Поможет только меньше экзекьюторов или разговор с платформой.

Джоб при этом не падает: Spark ждёт ресурсы и пишет `Initial job has not accepted any resources`.

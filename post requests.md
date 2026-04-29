Основные post запросы для получения данных из 1С:

1) получение данных по документу из 1С:
http://kaz-app01-pub.technoavia.ru/KAZ-UT11-5/odata/standard.odata/Document_СчетФактураВыданный(guid'8b6b0114-42e2-11f1-92c8-00155d060d01')?$select=Date,ПредставлениеНомера,Корректировочный&$format=json
Где guid - это guid документа из 1С. полученный после конвертаци barcode в guid

Если у документа корректировочный true - то это укд, если false - то это упд.
ПредставлениеНомера - это номер документа из 1С.

Получение данных по перемещению товаров из 1С:
http://kaz-app01-pub.technoavia.ru/KAZ-UT11-5/odata/standard.odata/Document_ПеремещениеТоваров(guid'8b6b0114-42e2-11f1-92c8-00155d060d01')?$format=json&$select=Date,Number
Где guid - это guid документа из 1С. полученный после конвертаци barcode в guid

# Paperless matching dry-run sample

Дата: 2026-05-21

Это dry-run после реализации умного матчинга корреспондента: локальная БД не изменялась, PATCH в 1С не отправлялся. Поля `DB write` и `1C PATCH` показывают, что было бы записано/отправлено при фактической обработке.

UNC-root для примера: `\\paperless-server\paperless-media\documents\originals`. Его нужно заменить на реальный сетевой путь, доступный Windows/1С.

## Summary

- Sample size: 10 random Paperless documents of type УПД/УКД.
- Matched by implemented matcher: 10/10.
- Not matched: 0/10.
- Hard filters: document date + document number. Correspondent is matched after normalization, abbreviation expansion, known aliases, and fuzzy/token score.

## Compact Results

| Paperless ID | Type | Title | Paperless correspondent | Extracted number | DB candidates by date+number | Selected DB partner | Best score | Status |
|---:|---|---|---|---|---:|---|---:|---|
| 1809 | УПД | 04.02.2026 УПД № УТ-762 ИТЦ ТЕПЛОВИК ООО | ИТЦ ТЕПЛОВИК ООО | УТ-762 | 1 | ИТЦ ТЕПЛОВИК ООО | 1.0 | matched |
| 1923 | УПД | 12.02.2026 УПД № УТ-961 НПП "ГКС" | НПП "ГКС" | УТ-961 | 1 | ООО НПП "ГКС" | 1.0 | matched |
| 1902 | УПД | 11.02.2026 УПД № УТ-894 СафПласт | СафПласт | УТ-894 | 1 | ООО "СафПласт" | 1.0 | matched |
| 1888 | УПД | 16.02.2026 УПД № УТ-1077 ТАТХИМФАРМПРЕПАРАТЫ АО | ТАТХИМФАРМПРЕПАРАТЫ АО | УТ-1077 | 1 | АО "Татхимфармпрепараты" | 1.0 | matched |
| 2001 | УПД | 05.02.2026 УПД № УТ-655 ИП Григорьев Сергей Вячеславович | ИП Григорьев Сергей Вячеславович | УТ-655 | 1 | ИП Григорьев Сергей Вячеславович | 1.0 | matched |
| 1998 | УПД | 05.02.2026 УПД № УТ-628 ЗЗСГ ООО | ЗЗСГ ООО | УТ-628 | 1 | ЗЗСГ ООО | 1.0 | matched |
| 1967 | УПД | 04.02.2026 УПД № УТ-688 АПА-СЕРВИС ООО | АПА-СЕРВИС ООО | УТ-688 | 1 | АПА-СЕРВИС ООО | 1.0 | matched |
| 1821 | УПД | 05.02.2026 УПД № УТ-833 ИП Сиора Игорь Иванович | ИП Сиора Игорь Иванович | УТ-833 | 1 | Сиора Игорь Иванович | 1.0 | matched |
| 1997 | УПД | 05.02.2026 УПД № УТ-630 ЗАО СКБ "ХРОМАТЭК" | ЗАО СКБ "ХРОМАТЭК" | УТ-630 | 1 | ЗАО СКБ "Хроматэк" | 1.0 | matched |
| 1806 | УПД | 04.02.2026 УПД № УТ-754 ИП Бикмуллин И.Р. | ИП Бикмуллин И.Р. | УТ-754 | 1 | ИП Бикмуллин И.Р. | 1.0 | matched |

## Per-document Dry Run

### 1. Paperless document 1809

Paperless received:

```json
{
  "document_id": 1809,
  "file_name": "04.02.2026 УПД № УТ-762 ИТЦ ТЕПЛОВИК ООО",
  "doc_type": "УПД",
  "created": "2026-02-04",
  "correspondent": "ИТЦ ТЕПЛОВИК ООО",
  "download_url": "http://localhost:8000/api/documents/1809/download/",
  "original_filename": "Untitled - 0031.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-762 ИТЦ ТЕПЛОВИК ООО.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/04.02.2026 УПД № УТ-762 ИТЦ ТЕПЛОВИК ООО.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-762",
  "digits_only": "762",
  "match_guid": "a06a2122-01cc-11f1-92b0-00155d060d01",
  "match_print_number": "УТ-762",
  "match_partner_name": "ИТЦ ТЕПЛОВИК ООО",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "a06a2122-01cc-11f1-92b0-00155d060d01",
      "number": "ТАУТ-0000762",
      "print_number": "УТ-762",
      "doc_date": "2026-02-04",
      "partner_name": "ИТЦ ТЕПЛОВИК ООО",
      "normalized_paperless": "итц тепловик",
      "normalized_1c": "итц тепловик",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "a06a2122-01cc-11f1-92b0-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-762 ИТЦ ТЕПЛОВИК ООО.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1809/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-762 ИТЦ ТЕПЛОВИК ООО.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'a06a2122-01cc-11f1-92b0-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-762 ИТЦ ТЕПЛОВИК ООО.pdf"
  }
}
```

### 2. Paperless document 1923

Paperless received:

```json
{
  "document_id": 1923,
  "file_name": "12.02.2026 УПД № УТ-961 НПП \"ГКС\"",
  "doc_type": "УПД",
  "created": "2026-02-12",
  "correspondent": "НПП \"ГКС\"",
  "download_url": "http://localhost:8000/api/documents/1923/download/",
  "original_filename": "Untitled - 0161.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\12.02.2026 УПД № УТ-961 НПП -ГКС-.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/12.02.2026 УПД № УТ-961 НПП -ГКС-.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-961",
  "digits_only": "961",
  "match_guid": "c9f3ff8c-071b-11f1-92b2-00155d060d01",
  "match_print_number": "УТ-961",
  "match_partner_name": "ООО НПП \"ГКС\"",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "c9f3ff8c-071b-11f1-92b2-00155d060d01",
      "number": "ТАУТ-0000961",
      "print_number": "УТ-961",
      "doc_date": "2026-02-12",
      "partner_name": "ООО НПП \"ГКС\"",
      "normalized_paperless": "нпп гкс",
      "normalized_1c": "нпп гкс",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "c9f3ff8c-071b-11f1-92b2-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\12.02.2026 УПД № УТ-961 НПП -ГКС-.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1923/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\12.02.2026 УПД № УТ-961 НПП -ГКС-.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'c9f3ff8c-071b-11f1-92b2-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\12.02.2026 УПД № УТ-961 НПП -ГКС-.pdf"
  }
}
```

### 3. Paperless document 1902

Paperless received:

```json
{
  "document_id": 1902,
  "file_name": "11.02.2026 УПД № УТ-894 СафПласт",
  "doc_type": "УПД",
  "created": "2026-02-11",
  "correspondent": "СафПласт",
  "download_url": "http://localhost:8000/api/documents/1902/download/",
  "original_filename": "1897_1896_merged.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\11.02.2026 УПД № УТ-894 СафПласт.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/11.02.2026 УПД № УТ-894 СафПласт.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-894",
  "digits_only": "894",
  "match_guid": "0e563566-0665-11f1-92b1-00155d060d01",
  "match_print_number": "УТ-894",
  "match_partner_name": "ООО \"СафПласт\"",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "0e563566-0665-11f1-92b1-00155d060d01",
      "number": "ТАУТ-0000894",
      "print_number": "УТ-894",
      "doc_date": "2026-02-11",
      "partner_name": "ООО \"СафПласт\"",
      "normalized_paperless": "сафпласт",
      "normalized_1c": "сафпласт",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "0e563566-0665-11f1-92b1-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\11.02.2026 УПД № УТ-894 СафПласт.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1902/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\11.02.2026 УПД № УТ-894 СафПласт.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'0e563566-0665-11f1-92b1-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\11.02.2026 УПД № УТ-894 СафПласт.pdf"
  }
}
```

### 4. Paperless document 1888

Paperless received:

```json
{
  "document_id": 1888,
  "file_name": "16.02.2026 УПД № УТ-1077 ТАТХИМФАРМПРЕПАРАТЫ АО",
  "doc_type": "УПД",
  "created": "2026-02-16",
  "correspondent": "ТАТХИМФАРМПРЕПАРАТЫ АО",
  "download_url": "http://localhost:8000/api/documents/1888/download/",
  "original_filename": "Untitled - 0128.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\16.02.2026 УПД № УТ-1077 ТАТХИМФАРМПРЕПАРАТЫ АО.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/16.02.2026 УПД № УТ-1077 ТАТХИМФАРМПРЕПАРАТЫ АО.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-1077",
  "digits_only": "1077",
  "match_guid": "54eb7ee7-0b05-11f1-92b3-00155d060d01",
  "match_print_number": "УТ-1077",
  "match_partner_name": "АО \"Татхимфармпрепараты\"",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "54eb7ee7-0b05-11f1-92b3-00155d060d01",
      "number": "ТАУТ-0001077",
      "print_number": "УТ-1077",
      "doc_date": "2026-02-16",
      "partner_name": "АО \"Татхимфармпрепараты\"",
      "normalized_paperless": "татхимфармпрепараты",
      "normalized_1c": "татхимфармпрепараты",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "54eb7ee7-0b05-11f1-92b3-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\16.02.2026 УПД № УТ-1077 ТАТХИМФАРМПРЕПАРАТЫ АО.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1888/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\16.02.2026 УПД № УТ-1077 ТАТХИМФАРМПРЕПАРАТЫ АО.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'54eb7ee7-0b05-11f1-92b3-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\16.02.2026 УПД № УТ-1077 ТАТХИМФАРМПРЕПАРАТЫ АО.pdf"
  }
}
```

### 5. Paperless document 2001

Paperless received:

```json
{
  "document_id": 2001,
  "file_name": "05.02.2026 УПД № УТ-655 ИП Григорьев Сергей Вячеславович",
  "doc_type": "УПД",
  "created": "2026-02-05",
  "correspondent": "ИП Григорьев Сергей Вячеславович",
  "download_url": "http://localhost:8000/api/documents/2001/download/",
  "original_filename": "Untitled - 0242.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-655 ИП Григорьев Сергей Вячеславович.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/05.02.2026 УПД № УТ-655 ИП Григорьев Сергей Вячеславович.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-655",
  "digits_only": "655",
  "match_guid": "f9acee43-00ec-11f1-92af-00155d060d01",
  "match_print_number": "УТ-655",
  "match_partner_name": "ИП Григорьев Сергей Вячеславович",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "f9acee43-00ec-11f1-92af-00155d060d01",
      "number": "ТАУТ-0000655",
      "print_number": "УТ-655",
      "doc_date": "2026-02-05",
      "partner_name": "ИП Григорьев Сергей Вячеславович",
      "normalized_paperless": "григорьев сергей вячеславович",
      "normalized_1c": "григорьев сергей вячеславович",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "f9acee43-00ec-11f1-92af-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-655 ИП Григорьев Сергей Вячеславович.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/2001/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-655 ИП Григорьев Сергей Вячеславович.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'f9acee43-00ec-11f1-92af-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-655 ИП Григорьев Сергей Вячеславович.pdf"
  }
}
```

### 6. Paperless document 1998

Paperless received:

```json
{
  "document_id": 1998,
  "file_name": "05.02.2026 УПД № УТ-628 ЗЗСГ ООО",
  "doc_type": "УПД",
  "created": "2026-02-05",
  "correspondent": "ЗЗСГ ООО",
  "download_url": "http://localhost:8000/api/documents/1998/download/",
  "original_filename": "1996_1995_merged.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-628 ЗЗСГ ООО.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/05.02.2026 УПД № УТ-628 ЗЗСГ ООО.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-628",
  "digits_only": "628",
  "match_guid": "eaf3bfbc-00d1-11f1-92af-00155d060d01",
  "match_print_number": "УТ-628",
  "match_partner_name": "ЗЗСГ ООО",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "eaf3bfbc-00d1-11f1-92af-00155d060d01",
      "number": "ТАУТ-0000628",
      "print_number": "УТ-628",
      "doc_date": "2026-02-05",
      "partner_name": "ЗЗСГ ООО",
      "normalized_paperless": "ззсг",
      "normalized_1c": "ззсг",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "eaf3bfbc-00d1-11f1-92af-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-628 ЗЗСГ ООО.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1998/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-628 ЗЗСГ ООО.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'eaf3bfbc-00d1-11f1-92af-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-628 ЗЗСГ ООО.pdf"
  }
}
```

### 7. Paperless document 1967

Paperless received:

```json
{
  "document_id": 1967,
  "file_name": "04.02.2026 УПД № УТ-688 АПА-СЕРВИС ООО",
  "doc_type": "УПД",
  "created": "2026-02-04",
  "correspondent": "АПА-СЕРВИС ООО",
  "download_url": "http://localhost:8000/api/documents/1967/download/",
  "original_filename": "1965_1964_merged.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-688 АПА-СЕРВИС ООО.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/04.02.2026 УПД № УТ-688 АПА-СЕРВИС ООО.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-688",
  "digits_only": "688",
  "match_guid": "542b59f5-0101-11f1-92af-00155d060d01",
  "match_print_number": "УТ-688",
  "match_partner_name": "АПА-СЕРВИС ООО",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "542b59f5-0101-11f1-92af-00155d060d01",
      "number": "ТАУТ-0000688",
      "print_number": "УТ-688",
      "doc_date": "2026-02-04",
      "partner_name": "АПА-СЕРВИС ООО",
      "normalized_paperless": "апа сервис",
      "normalized_1c": "апа сервис",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "542b59f5-0101-11f1-92af-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-688 АПА-СЕРВИС ООО.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1967/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-688 АПА-СЕРВИС ООО.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'542b59f5-0101-11f1-92af-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-688 АПА-СЕРВИС ООО.pdf"
  }
}
```

### 8. Paperless document 1821

Paperless received:

```json
{
  "document_id": 1821,
  "file_name": "05.02.2026 УПД № УТ-833 ИП Сиора Игорь Иванович",
  "doc_type": "УПД",
  "created": "2026-02-05",
  "correspondent": "ИП Сиора Игорь Иванович",
  "download_url": "http://localhost:8000/api/documents/1821/download/",
  "original_filename": "Untitled - 0048.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-833 ИП Сиора Игорь Иванович.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/05.02.2026 УПД № УТ-833 ИП Сиора Игорь Иванович.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-833",
  "digits_only": "833",
  "match_guid": "19b34b43-0298-11f1-92b0-00155d060d01",
  "match_print_number": "УТ-833",
  "match_partner_name": "Сиора Игорь Иванович",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "19b34b43-0298-11f1-92b0-00155d060d01",
      "number": "ТАУТ-0000833",
      "print_number": "УТ-833",
      "doc_date": "2026-02-05",
      "partner_name": "Сиора Игорь Иванович",
      "normalized_paperless": "сиора игорь иванович",
      "normalized_1c": "сиора игорь иванович",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "19b34b43-0298-11f1-92b0-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-833 ИП Сиора Игорь Иванович.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1821/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-833 ИП Сиора Игорь Иванович.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'19b34b43-0298-11f1-92b0-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-833 ИП Сиора Игорь Иванович.pdf"
  }
}
```

### 9. Paperless document 1997

Paperless received:

```json
{
  "document_id": 1997,
  "file_name": "05.02.2026 УПД № УТ-630 ЗАО СКБ \"ХРОМАТЭК\"",
  "doc_type": "УПД",
  "created": "2026-02-05",
  "correspondent": "ЗАО СКБ \"ХРОМАТЭК\"",
  "download_url": "http://localhost:8000/api/documents/1997/download/",
  "original_filename": "Untitled - 0239.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-630",
  "digits_only": "630",
  "match_guid": "f63549a7-00d2-11f1-92af-00155d060d01",
  "match_print_number": "УТ-630",
  "match_partner_name": "ЗАО СКБ \"Хроматэк\"",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "f63549a7-00d2-11f1-92af-00155d060d01",
      "number": "ТАУТ-0000630",
      "print_number": "УТ-630",
      "doc_date": "2026-02-05",
      "partner_name": "ЗАО СКБ \"Хроматэк\"",
      "normalized_paperless": "скб хроматэк",
      "normalized_1c": "скб хроматэк",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "f63549a7-00d2-11f1-92af-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1997/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'f63549a7-00d2-11f1-92af-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\05.02.2026 УПД № УТ-630 ЗАО СКБ -ХРОМАТЭК-.pdf"
  }
}
```

### 10. Paperless document 1806

Paperless received:

```json
{
  "document_id": 1806,
  "file_name": "04.02.2026 УПД № УТ-754 ИП Бикмуллин И.Р.",
  "doc_type": "УПД",
  "created": "2026-02-04",
  "correspondent": "ИП Бикмуллин И.Р.",
  "download_url": "http://localhost:8000/api/documents/1806/download/",
  "original_filename": "Untitled - 0027.pdf",
  "archive_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-754 ИП Бикмуллин И.Р.pdf"
}
```

Paperless storage metadata:

```json
{
  "storage_path": null,
  "archived_file_name": null,
  "metadata.media_filename": "2026/февр./УПД/04.02.2026 УПД № УТ-754 ИП Бикмуллин И.Р.pdf",
  "metadata.has_archive_version": false,
  "metadata.archive_media_filename": null,
  "unc_source_field": "media_filename"
}
```

Local DB lookup and selected match:

```json
{
  "doc_number": "УТ-754",
  "digits_only": "754",
  "match_guid": "b35366f6-01c5-11f1-92b0-00155d060d01",
  "match_print_number": "УТ-754",
  "match_partner_name": "ИП Бикмуллин И.Р.",
  "candidate_count_by_date_number": 1,
  "candidates": [
    {
      "guid": "b35366f6-01c5-11f1-92b0-00155d060d01",
      "number": "ТАУТ-0000754",
      "print_number": "УТ-754",
      "doc_date": "2026-02-04",
      "partner_name": "ИП Бикмуллин И.Р.",
      "normalized_paperless": "бикмуллин и р",
      "normalized_1c": "бикмуллин и р",
      "partner_score": 1.0,
      "kzv_copy_link_before": null,
      "archive_storage_path_before": null,
      "archive_download_url_before": null
    }
  ]
}
```

DB write dry-run:

```json
{
  "where": {
    "guid": "b35366f6-01c5-11f1-92b0-00155d060d01"
  },
  "values": {
    "archive_processed_at": "<now UTC>",
    "archive_storage_path": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-754 ИП Бикмуллин И.Р.pdf",
    "archive_download_url": "http://localhost:8000/api/documents/1806/download/",
    "kzv_copy_link": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-754 ИП Бикмуллин И.Р.pdf"
  }
}
```

1C PATCH dry-run:

```json
{
  "method": "PATCH",
  "url": "/Document_СчетФактураВыданный(guid'b35366f6-01c5-11f1-92b0-00155d060d01')?$format=json",
  "json": {
    "kzvСсылкаНаКопию": "\\\\paperless-server\\paperless-media\\documents\\originals\\2026\\февр.\\УПД\\04.02.2026 УПД № УТ-754 ИП Бикмуллин И.Р.pdf"
  }
}
```

## Implemented Matching Strategy

- The service now requires both document date and document number before looking at correspondent names.
- Paperless and 1C partner names are normalized: casefold, `ё` -> `е`, punctuation removal, legal-form token removal.
- Common abbreviations are expanded, including `ТД`, `ТК`, `НПО`, `УК`.
- Known short aliases are handled explicitly; currently `КАП` maps to `Казанское Авиапредприятие`.
- For one date+number candidate, the correspondent score must be at least `0.86` unless correspondent is absent.
- For multiple candidates, the best score must be at least `0.90` and beat the second score by `0.08`; otherwise the document stays unmatched/ambiguous and 1C is not patched.

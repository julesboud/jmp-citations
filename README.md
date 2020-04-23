# jmp-citations

Python modules to get citation counts of PDF articles (current application is for economics job market papers).

`jmp_title_parser.py` parses the PDF to find the article's title and name of its authors.

`scholarly_jmp.py` scrapes Google Scholar to retrieve its number of citations, year of publication, and number of authors. Leverages the [`scholarly`](https://github.com/OrganicIrradiation/scholarly) package.

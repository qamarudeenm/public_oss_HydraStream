{% macro confluent__get_table_columns_and_constraints() %}
  {% set columns = model.get('columns', {}).values() %}
  {% set column_specs = [] %}
  {% set raw_cols = model.get('columns', {}) %}
  {{ log("DEBUG_COLS_KEYS: " ~ raw_cols.keys() | list, info=True) }}
  {% for column in columns %}
    {{ log("DEBUG_COL: name=" ~ column.name ~ " column=" ~ column.column ~ " data_type=" ~ column.data_type ~ " quoted=" ~ column.quoted, info=True) }}
    {% set column_name = column.name %}
    {% set data_type = column.data_type %}
    {% if data_type == 'TEXT' %}
      {% set data_type = 'STRING' %}
    {% endif %}
    {% do column_specs.append("`" ~ column_name ~ "` " ~ data_type) %}
  {% endfor %}
  
  ({{ column_specs | join(',\n    ') }})
{% endmacro %}


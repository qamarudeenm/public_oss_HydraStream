{% macro confluent__type_string() %}
  {{ return('STRING') }}
{% endmacro %}

{% macro confluent__type_timestamp() %}
  {{ return('TIMESTAMP(3)') }}
{% endmacro %}

{% macro drop_flink_tables() %}
    {% if execute %}
        {% for node in graph.nodes.values() | selectattr("resource_type", "equalto", "model") %}
            {% set drop_query %}
                DROP TABLE IF EXISTS `{{ node.config.database | default('default_catalog') }}`.`{{ node.config.schema | default('default_database') }}`.`{{ node.name }}`
            {% endset %}
            {% do log("HydraStream: Pre-run cleanup - Dropping " ~ node.name, info=True) %}
            {% do run_query(drop_query) %}
        {% endfor %}
    {% endif %}
{% endmacro %}

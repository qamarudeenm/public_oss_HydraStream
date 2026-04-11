# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from flink_gateway_proxy.translator.drivers import detect_required_drivers, DRIVER_REGISTRY

def test_detect_mysql_driver():
    sql = """
    CREATE TABLE my_table (
        id INT,
        name STRING
    ) WITH (
        'connector' = 'jdbc',
        'url' = 'jdbc:mysql://localhost:3306/db',
        'table-name' = 'users',
        'driver' = 'com.mysql.jdbc.Driver'
    )
    """
    urls = detect_required_drivers(sql)
    assert DRIVER_REGISTRY["com.mysql.jdbc.Driver"] in urls

def test_detect_no_driver():
    sql = "SELECT * FROM my_table"
    urls = detect_required_drivers(sql)
    assert len(urls) == 0

def test_detect_multiple_drivers():
    sql = """
    CREATE TABLE t1 WITH ('driver' = 'com.mysql.jdbc.Driver');
    CREATE TABLE t2 WITH ('driver' = 'org.postgresql.Driver');
    """
    urls = detect_required_drivers(sql)
    assert DRIVER_REGISTRY["com.mysql.jdbc.Driver"] in urls
    assert DRIVER_REGISTRY["org.postgresql.Driver"] in urls

def test_case_insensitivity():
    sql = "CREATE TABLE t1 WITH ('DRIVER' = 'com.mysql.jdbc.Driver')"
    urls = detect_required_drivers(sql)
    assert DRIVER_REGISTRY["com.mysql.jdbc.Driver"] in urls

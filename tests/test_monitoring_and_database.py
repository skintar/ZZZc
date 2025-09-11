#!/usr/bin/env python3
"""
Тесты для системы мониторинга и базы данных.
"""

import pytest
import time
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Импортируем модули для тестирования
try:
    from monitoring import HealthMonitor, BotMetricsCollector, AlertSeverity, measure_time
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

try:
    from database import DatabaseManager
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False


@pytest.mark.skipif(not MONITORING_AVAILABLE, reason="Модуль мониторинга недоступен")
class TestHealthMonitor:
    """Тесты системы мониторинга."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.monitor = HealthMonitor()

    def test_add_metric(self):
        """Тест добавления метрики."""
        self.monitor.add_metric("test_metric", 42.5, {"tag": "value"})
        
        assert len(self.monitor.metrics) == 1
        metric = self.monitor.metrics[0]
        assert metric.name == "test_metric"
        assert metric.value == 42.5
        assert metric.tags == {"tag": "value"}

    def test_metric_cleanup(self):
        """Тест очистки старых метрик."""
        # Добавляем старую метрику
        old_time = datetime.now() - timedelta(hours=25)
        self.monitor.metrics.append(
            self.monitor.MetricPoint("old_metric", 10, old_time)
        )
        
        # Добавляем новую метрику
        self.monitor.add_metric("new_metric", 20)
        
        # Старая метрика должна быть удалена
        assert len(self.monitor.metrics) == 1
        assert self.monitor.metrics[0].name == "new_metric"

    def test_threshold_alerts(self):
        """Тест создания алертов при превышении порогов."""
        # Устанавливаем низкий порог для тестирования
        self.monitor.thresholds["test_metric"] = {"warning": 50, "critical": 100}
        
        # Добавляем метрику с критическим значением
        self.monitor.add_metric("test_metric", 150)
        
        # Должен быть создан критический алерт
        assert len(self.monitor.alerts) == 1
        alert = self.monitor.alerts[0]
        assert alert.severity == AlertSeverity.CRITICAL
        assert "test_metric" in alert.message

    def test_metrics_summary(self):
        """Тест получения сводки метрик."""
        # Добавляем несколько метрик
        self.monitor.add_metric("cpu_usage", 10)
        self.monitor.add_metric("cpu_usage", 20)
        self.monitor.add_metric("memory_usage", 30)
        
        summary = self.monitor.get_metrics_summary(1)
        
        assert "cpu_usage" in summary
        assert "memory_usage" in summary
        assert summary["cpu_usage"]["count"] == 2
        assert summary["cpu_usage"]["avg"] == 15
        assert summary["memory_usage"]["latest"] == 30

    def test_export_json(self):
        """Тест экспорта метрик в JSON."""
        self.monitor.add_metric("test_metric", 42)
        
        json_data = self.monitor.export_metrics_json(1)
        
        assert "metrics" in json_data
        assert "alerts" in json_data
        assert "summary" in json_data

    def test_export_prometheus(self):
        """Тест экспорта в формат Prometheus."""
        self.monitor.add_metric("test_metric", 42, {"service": "bot"})
        
        prometheus_data = self.monitor.export_prometheus()
        
        assert "test_metric" in prometheus_data
        assert "42" in prometheus_data
        assert 'service="bot"' in prometheus_data


@pytest.mark.skipif(not MONITORING_AVAILABLE, reason="Модуль мониторинга недоступен")
class TestBotMetricsCollector:
    """Тесты сборщика метрик бота."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.monitor = HealthMonitor()
        self.collector = BotMetricsCollector(self.monitor)

    def test_record_request_time(self):
        """Тест записи времени запроса."""
        self.collector.record_request_time(150.5, user_id=123)
        
        assert len(self.collector.request_times) == 1
        assert self.collector.request_times[0] == 150.5
        assert self.collector.request_count == 1

    def test_record_error(self):
        """Тест записи ошибки."""
        self.collector.request_count = 10
        self.collector.record_error("ValueError")
        
        assert self.collector.error_count == 1

    def test_error_rate_calculation(self):
        """Тест вычисления частоты ошибок."""
        self.collector.request_count = 100
        self.collector.record_error()
        
        # Проверяем, что метрика error_rate была добавлена
        error_rate_metrics = [m for m in self.monitor.metrics if m.name == "error_rate"]
        assert len(error_rate_metrics) > 0
        assert error_rate_metrics[0].value == 0.01  # 1/100

    def test_session_count_recording(self):
        """Тест записи количества сессий."""
        self.collector.record_session_count(42)
        
        session_metrics = [m for m in self.monitor.metrics if m.name == "active_sessions"]
        assert len(session_metrics) == 1
        assert session_metrics[0].value == 42


@pytest.mark.skipif(not MONITORING_AVAILABLE, reason="Модуль мониторинга недоступен")
class TestMeasureTimeDecorator:
    """Тесты декоратора измерения времени."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        # Патчим глобальные объекты для изоляции тестов
        self.monitor_mock = Mock()
        self.collector_mock = Mock()

    @patch('monitoring.health_monitor')
    @patch('monitoring.bot_metrics')
    def test_sync_function_measurement(self, mock_collector, mock_monitor):
        """Тест измерения времени синхронной функции."""
        @measure_time("test_function")
        def test_func():
            time.sleep(0.01)  # 10ms
            return "result"

        result = test_func()
        
        assert result == "result"
        assert mock_collector.record_request_time.called
        assert mock_monitor.add_metric.called

    @patch('monitoring.health_monitor')
    @patch('monitoring.bot_metrics')
    @pytest.mark.asyncio
    async def test_async_function_measurement(self, mock_collector, mock_monitor):
        """Тест измерения времени асинхронной функции."""
        @measure_time("test_async_function")
        async def test_async_func():
            await asyncio.sleep(0.01)  # 10ms
            return "async_result"

        result = await test_async_func()
        
        assert result == "async_result"
        assert mock_collector.record_request_time.called
        assert mock_monitor.add_metric.called

    @patch('monitoring.health_monitor')
    @patch('monitoring.bot_metrics')
    def test_exception_handling(self, mock_collector, mock_monitor):
        """Тест обработки исключений в декораторе."""
        @measure_time("test_error_function")
        def error_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            error_func()
        
        assert mock_collector.record_error.called


@pytest.mark.skipif(not DATABASE_AVAILABLE, reason="Модуль базы данных недоступен")
class TestDatabaseManager:
    """Тесты менеджера базы данных."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        # Создаем временную базу данных
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = DatabaseManager(self.temp_db.name)

    def teardown_method(self):
        """Очистка после каждого теста."""
        self.db.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_database_initialization(self):
        """Тест инициализации базы данных."""
        # Проверяем, что таблицы созданы
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN 
                ('active_sessions', 'global_rankings', 'new_characters', 'performance_metrics')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
        assert len(tables) == 4
        assert 'active_sessions' in tables
        assert 'global_rankings' in tables

    def test_save_and_load_session(self):
        """Тест сохранения и загрузки сессии."""
        session_data = {
            "characters_count": 10,
            "max_comparisons": 50,
            "comparisons_made": 5,
            "results": {"(0,1)": 0},
            "wins": {"0": 3, "1": 2},
            "choice_history": [((0, 1), 0)],
            "learned_preferences": {"0>1": 0.8}
        }
        
        # Сохраняем сессию
        self.db.save_session(123, session_data)
        
        # Загружаем сессию
        loaded_session = self.db.load_session(123)
        
        assert loaded_session is not None
        assert loaded_session["characters_count"] == 10
        assert loaded_session["comparisons_made"] == 5
        assert loaded_session["results"] == {"(0,1)": 0}

    def test_session_not_found(self):
        """Тест загрузки несуществующей сессии."""
        session = self.db.load_session(999)
        assert session is None

    def test_delete_session(self):
        """Тест удаления сессии."""
        session_data = {"characters_count": 5, "comparisons_made": 0}
        
        # Сохраняем и удаляем
        self.db.save_session(123, session_data)
        self.db.delete_session(123)
        
        # Проверяем, что сессия удалена
        loaded_session = self.db.load_session(123)
        assert loaded_session is None

    def test_global_ranking_operations(self):
        """Тест операций с глобальными рейтингами."""
        ranking = ["Персонаж1", "Персонаж2", "Персонаж3"]
        
        # Сохраняем рейтинг
        self.db.save_global_ranking(123, ranking)
        
        # Загружаем все рейтинги
        rankings = self.db.get_global_rankings()
        
        assert 123 in rankings
        assert rankings[123] == ranking

    def test_performance_metrics(self):
        """Тест работы с метриками производительности."""
        # Добавляем метрики
        self.db.add_performance_metric("response_time", 150.5, 123)
        self.db.add_performance_metric("cpu_usage", 75.0)
        
        # Получаем метрики
        metrics = self.db.get_performance_metrics("response_time", 24)
        
        assert len(metrics) == 1
        assert metrics[0]["metric_name"] == "response_time"
        assert metrics[0]["metric_value"] == 150.5
        assert metrics[0]["user_id"] == 123

    def test_cleanup_old_sessions(self):
        """Тест очистки старых сессий."""
        session_data = {"characters_count": 5, "comparisons_made": 0}
        
        # Сохраняем сессию
        self.db.save_session(123, session_data)
        
        # Имитируем старую сессию (изменяем updated_at в прошлое)
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE active_sessions 
                SET updated_at = datetime('now', '-25 hours')
                WHERE user_id = 123
            """)
            conn.commit()
        
        # Очищаем старые сессии
        deleted_count = self.db.cleanup_old_sessions(24)
        
        assert deleted_count == 1
        
        # Проверяем, что сессия удалена
        session = self.db.load_session(123)
        assert session is None

    def test_database_stats(self):
        """Тест получения статистики базы данных."""
        # Добавляем тестовые данные
        self.db.save_session(123, {"characters_count": 5, "comparisons_made": 0})
        self.db.save_global_ranking(123, ["Test"])
        self.db.add_performance_metric("test", 1.0)
        
        stats = self.db.get_database_stats()
        
        assert "active_sessions" in stats
        assert "global_rankings" in stats
        assert "performance_metrics" in stats
        assert stats["active_sessions"] == 1
        assert stats["global_rankings"] == 1
        assert stats["performance_metrics"] == 1

    def test_vacuum_database(self):
        """Тест оптимизации базы данных."""
        # Просто проверяем, что операция не падает
        self.db.vacuum_database()


# Интеграционные тесты
@pytest.mark.skipif(not (MONITORING_AVAILABLE and DATABASE_AVAILABLE), 
                   reason="Модули мониторинга и БД недоступны")
class TestIntegration:
    """Интеграционные тесты."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = DatabaseManager(self.temp_db.name)
        self.monitor = HealthMonitor()

    def teardown_method(self):
        """Очистка после каждого теста."""
        self.db.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_metrics_to_database_flow(self):
        """Тест потока от мониторинга к базе данных."""
        # Добавляем метрики в монитор
        self.monitor.add_metric("response_time", 125.5)
        self.monitor.add_metric("cpu_usage", 45.0)
        
        # Сохраняем метрики в базу данных
        for metric in self.monitor.metrics:
            self.db.add_performance_metric(
                metric.name, 
                metric.value
            )
        
        # Проверяем, что метрики сохранились
        db_metrics = self.db.get_performance_metrics()
        assert len(db_metrics) == 2
        
        metric_names = [m["metric_name"] for m in db_metrics]
        assert "response_time" in metric_names
        assert "cpu_usage" in metric_names


if __name__ == "__main__":
    # Запуск тестов
    import sys
    
    if MONITORING_AVAILABLE:
        print("✅ Модуль мониторинга доступен")
    else:
        print("⚠️ Модуль мониторинга недоступен")
    
    if DATABASE_AVAILABLE:
        print("✅ Модуль базы данных доступен")
    else:
        print("⚠️ Модуль базы данных недоступен")
    
    # Запускаем pytest
    sys.exit(pytest.main([__file__, "-v"]))
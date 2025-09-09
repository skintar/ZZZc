#!/usr/bin/env python3
"""
Скрипт для мониторинга состояния бота и анализа статистики.
"""

import os
import json
import logging
import asyncio
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

@dataclass
class SystemMetrics:
    """Метрики системы."""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    active_sessions: int = 0
    requests_per_minute: int = 0
    error_rate: float = 0.0
    uptime: int = 0  # в секундах
    timestamp: str = ""


@dataclass
class AlertRule:
    """Правило для оповещений."""
    name: str
    metric: str
    threshold: float
    operator: str  # '>', '<', '>=', '<=', '=='
    severity: str  # 'low', 'medium', 'high', 'critical'
    enabled: bool = True


class MetricsCollector:
    """Класс для сбора метрик."""
    
    def __init__(self):
        self.start_time = time.time()
        self.request_times = deque(maxlen=100)  # Последние 100 запросов
        self.error_count = 0
        self.total_requests = 0
    
    def record_request(self):
        """Записывает запрос."""
        self.request_times.append(time.time())
        self.total_requests += 1
    
    def record_error(self):
        """Записывает ошибку."""
        self.error_count += 1
    
    def get_system_metrics(self) -> SystemMetrics:
        """Получает текущие метрики системы."""
        now = time.time()
        
        # Подсчитываем запросы в минуту
        recent_requests = [t for t in self.request_times if now - t < 60]
        requests_per_minute = len(recent_requests)
        
        # Подсчитываем частоту ошибок
        error_rate = (self.error_count / self.total_requests * 100) if self.total_requests > 0 else 0
        
        # Пытаемся получить системные метрики
        cpu_usage = 0.0
        memory_usage = 0.0
        disk_usage = 0.0
        
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('.').percent
        except ImportError:
            # psutil не установлен, используем заглушки
            pass
        except Exception:
            # Любые другие ошибки
            pass
        
        return SystemMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            active_sessions=0,  # Будет обновляться из сервисов
            requests_per_minute=requests_per_minute,
            error_rate=round(error_rate, 2),
            uptime=int(now - self.start_time),
            timestamp=datetime.now().isoformat()
        )


class AlertManager:
    """Менеджер оповещений."""
    
    def __init__(self):
        self.rules = [
            AlertRule("High CPU Usage", "cpu_usage", 80.0, ">", "high"),
            AlertRule("High Memory Usage", "memory_usage", 85.0, ">", "high"),
            AlertRule("High Disk Usage", "disk_usage", 90.0, ">", "critical"),
            AlertRule("High Error Rate", "error_rate", 5.0, ">", "medium"),
            AlertRule("Low Activity", "requests_per_minute", 1, "<", "low")
        ]
        self.alerts_history = deque(maxlen=100)
    
    def check_alerts(self, metrics: SystemMetrics) -> List[Dict[str, Any]]:
        """Проверяет алерты на основании метрик."""
        active_alerts = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            metric_value = getattr(metrics, rule.metric, 0)
            triggered = self._evaluate_condition(metric_value, rule.threshold, rule.operator)
            
            if triggered:
                alert = {
                    "rule_name": rule.name,
                    "metric": rule.metric,
                    "current_value": metric_value,
                    "threshold": rule.threshold,
                    "severity": rule.severity,
                    "timestamp": metrics.timestamp,
                    "message": f"{rule.name}: {metric_value} {rule.operator} {rule.threshold}"
                }
                active_alerts.append(alert)
                self.alerts_history.append(alert)
        
        return active_alerts
    
    def _evaluate_condition(self, value: float, threshold: float, operator: str) -> bool:
        """Оценивает условие алерта."""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        return False


class DashboardData:
    """Класс для хранения данных для дашборда."""
    
    def __init__(self):
        self.metrics_history = deque(maxlen=100)
        self.last_update = datetime.now()
    
    def add_metrics(self, metrics: SystemMetrics):
        """Добавляет метрики в историю."""
        self.metrics_history.append(asdict(metrics))
        self.last_update = datetime.now()
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Получает данные для дашборда."""
        if not self.metrics_history:
            return {}
        
        latest = self.metrics_history[-1]
        
        # Подсчитываем средние значения за последние 10 минут
        recent_metrics = list(self.metrics_history)[-10:]
        avg_cpu = sum(m['cpu_usage'] for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m['memory_usage'] for m in recent_metrics) / len(recent_metrics)
        
        return {
            "current": latest,
            "averages": {
                "cpu_usage": round(avg_cpu, 2),
                "memory_usage": round(avg_memory, 2)
            },
            "history": list(self.metrics_history)[-20:],  # Последние 20 точек
            "last_update": self.last_update.isoformat()
        }


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BotMonitor:
    """Класс для мониторинга состояния бота."""
    
    def __init__(self):
        self.data_dir = Path(".")
        self.characters_dir = Path("Персонажи")
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.dashboard_data = DashboardData()
        self._monitoring_active = False
        self._monitoring_thread = None
    
    def check_bot_status(self) -> Dict[str, Any]:
        """Проверяет общий статус бота."""
        status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "OK",
            "issues": [],
            "warnings": [],
            "statistics": {}
        }
        
        # Проверяем основные файлы
        if not self._check_config_files(status):
            status["overall_status"] = "ERROR"
        
        # Проверяем изображения персонажей
        if not self._check_character_images(status):
            status["overall_status"] = "WARNING"
        
        # Проверяем данные
        self._check_data_files(status)
        
        # Собираем статистику
        self._collect_statistics(status)
        
        return status
    
    def _check_config_files(self, status: Dict[str, Any]) -> bool:
        """Проверяет конфигурационные файлы."""
        required_files = ["config.py", "bot.py", "handlers.py", "services.py", "models.py"]
        
        for file_name in required_files:
            if not (self.data_dir / file_name).exists():
                status["issues"].append(f"Отсутствует файл: {file_name}")
                return False
        
        # Проверяем .env файл
        if not (self.data_dir / ".env").exists():
            status["warnings"].append("Файл .env не найден. Используйте env_example.txt как шаблон.")
        
        return True
    
    def _check_character_images(self, status: Dict[str, Any]) -> bool:
        """Проверяет изображения персонажей."""
        if not self.characters_dir.exists():
            status["issues"].append(f"Директория {self.characters_dir} не найдена")
            return False
        
        # Загружаем список персонажей из config.py
        try:
            import config
            character_names = config.CHARACTER_NAMES
        except ImportError:
            status["warnings"].append("Не удалось загрузить список персонажей из config.py")
            return False
        
        missing_images = []
        total_images = 0
        
        for character_name in character_names:
            image_path = self.characters_dir / f"{character_name}.png"
            if image_path.exists():
                total_images += 1
            else:
                missing_images.append(character_name)
        
        if missing_images:
            status["warnings"].append(f"Отсутствуют изображения для персонажей: {missing_images}")
        
        status["statistics"]["characters"] = {
            "total": len(character_names),
            "with_images": total_images,
            "missing": len(missing_images)
        }
        
        return len(missing_images) == 0
    
    def _check_data_files(self, status: Dict[str, Any]) -> None:
        """Проверяет файлы данных."""
        data_files = ["global_stats.json", "new_characters.json"]
        
        for file_name in data_files:
            file_path = self.data_dir / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if file_name == "global_stats.json":
                        status["statistics"]["users"] = len(data)
                    elif file_name == "new_characters.json":
                        status["statistics"]["new_characters"] = len(data)
                        
                except json.JSONDecodeError:
                    status["issues"].append(f"Поврежден файл данных: {file_name}")
            else:
                status["warnings"].append(f"Файл данных не найден: {file_name}")
    
    def _collect_statistics(self, status: Dict[str, Any]) -> None:
        """Собирает дополнительную статистику."""
        # Проверяем лог файл
        log_file = self.data_dir / "bot.log"
        if log_file.exists():
            try:
                size_mb = log_file.stat().st_size / (1024 * 1024)
                status["statistics"]["log_size_mb"] = round(size_mb, 2)
                
                # Подсчитываем количество строк в логе
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    status["statistics"]["log_lines"] = len(lines)
                    
                    # Подсчитываем ошибки
                    error_count = sum(1 for line in lines if "ERROR" in line)
                    status["statistics"]["errors_in_log"] = error_count
                    
            except Exception as e:
                status["warnings"].append(f"Не удалось проанализировать лог файл: {e}")
        
        # Проверяем бэкапы
        backup_files = list(self.data_dir.glob("global_stats.json.*"))
        status["statistics"]["backups"] = len(backup_files)
    
    def get_user_statistics(self) -> Dict[str, Any]:
        """Получает статистику пользователей."""
        stats_file = self.data_dir / "global_stats.json"
        
        if not stats_file.exists():
            return {"error": "Файл статистики не найден"}
        
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Анализируем данные пользователей
            user_count = len(data)
            total_ratings = sum(len(ratings) for ratings in data.values())
            
            # Находим самых активных пользователей
            user_activity = [(user_id, len(ratings)) for user_id, ratings in data.items()]
            user_activity.sort(key=lambda x: x[1], reverse=True)
            
            return {
                "total_users": user_count,
                "total_ratings": total_ratings,
                "average_ratings_per_user": round(total_ratings / user_count, 2) if user_count > 0 else 0,
                "most_active_users": user_activity[:5],
                "recent_activity": self._get_recent_activity()
            }
            
        except Exception as e:
            return {"error": f"Ошибка при анализе статистики: {e}"}
    
    def _get_recent_activity(self) -> List[Dict[str, Any]]:
        """Получает недавнюю активность из лога."""
        log_file = self.data_dir / "bot.log"
        recent_activity = []
        
        if not log_file.exists():
            return recent_activity
        
        try:
            # Читаем последние 100 строк лога
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-100:]
            
            # Ищем записи о создании рейтингов
            for line in lines:
                if "рейтинг" in line.lower() or "ranking" in line.lower():
                    recent_activity.append({
                        "timestamp": line.split(" - ")[0] if " - " in line else "Unknown",
                        "message": line.strip()
                    })
            
            return recent_activity[-10:]  # Последние 10 записей
            
        except Exception as e:
            logger.error(f"Ошибка при анализе лога: {e}")
            return recent_activity
    
    def generate_report(self) -> str:
        """Генерирует текстовый отчет о состоянии бота."""
        status = self.check_bot_status()
        user_stats = self.get_user_statistics()
        
        report = []
        report.append("=" * 50)
        report.append("ОТЧЕТ О СОСТОЯНИИ БОТА")
        report.append("=" * 50)
        report.append(f"Время: {status['timestamp']}")
        report.append(f"Статус: {status['overall_status']}")
        report.append("")
        
        # Проблемы
        if status["issues"]:
            report.append("🚨 ПРОБЛЕМЫ:")
            for issue in status["issues"]:
                report.append(f"  • {issue}")
            report.append("")
        
        # Предупреждения
        if status["warnings"]:
            report.append("⚠️ ПРЕДУПРЕЖДЕНИЯ:")
            for warning in status["warnings"]:
                report.append(f"  • {warning}")
            report.append("")
        
        # Статистика
        report.append("📊 СТАТИСТИКА:")
        stats = status["statistics"]
        
        if "characters" in stats:
            chars = stats["characters"]
            report.append(f"  • Персонажи: {chars['with_images']}/{chars['total']} (не хватает: {chars['missing']})")
        
        if "users" in stats:
            report.append(f"  • Пользователи: {stats['users']}")
        
        if "log_size_mb" in stats:
            report.append(f"  • Размер лога: {stats['log_size_mb']}MB ({stats['log_lines']} строк)")
        
        if "backups" in stats:
            report.append(f"  • Бэкапы: {stats['backups']}")
        
        if "errors_in_log" in stats:
            report.append(f"  • Ошибок в логе: {stats['errors_in_log']}")
        
        report.append("")
        
        # Статистика пользователей
        if "error" not in user_stats:
            report.append("👥 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ:")
            report.append(f"  • Всего пользователей: {user_stats['total_users']}")
            report.append(f"  • Всего рейтингов: {user_stats['total_ratings']}")
            report.append(f"  • Среднее рейтингов на пользователя: {user_stats['average_ratings_per_user']}")
            
            if user_stats['most_active_users']:
                report.append("  • Самые активные пользователи:")
                for i, (user_id, count) in enumerate(user_stats['most_active_users'][:3], 1):
                    report.append(f"    {i}. ID {user_id}: {count} рейтингов")
        
        report.append("")
        report.append("=" * 50)
        
        return "\n".join(report)
    
    def start_monitoring(self, interval: int = 30) -> None:
        """Запускает мониторинг в отдельном потоке."""
        if self._monitoring_active:
            logger.warning("Мониторинг уже активен")
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval,),
            daemon=True
        )
        self._monitoring_thread.start()
        logger.info(f"📊 Мониторинг запущен с интервалом {interval} секунд")
    
    def stop_monitoring(self) -> None:
        """Останавливает мониторинг."""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("❌ Мониторинг остановлен")
    
    def _monitoring_loop(self, interval: int) -> None:
        """Основной цикл мониторинга."""
        while self._monitoring_active:
            try:
                # Собираем метрики
                metrics = self.metrics_collector.get_system_metrics()
                
                # Обновляем данные для дашборда
                self.dashboard_data.add_metrics(metrics)
                
                # Проверяем алерты
                alerts = self.alert_manager.check_alerts(metrics)
                
                # Логируем алерты
                for alert in alerts:
                    severity_emoji = {
                        'low': '🟡',
                        'medium': '🟠', 
                        'high': '🔴',
                        'critical': '⚠️'
                    }
                    emoji = severity_emoji.get(alert['severity'], '🟡')
                    logger.warning(f"{emoji} ALERT: {alert['message']}")
                
                # Логируем общие метрики каждые 5 минут
                if int(time.time()) % 300 == 0:  # Каждые 5 минут
                    logger.info(
                        f"📊 CPU: {metrics.cpu_usage}%, "
                        f"RAM: {metrics.memory_usage}%, "
                        f"Requests/min: {metrics.requests_per_minute}, "
                        f"Error rate: {metrics.error_rate}%"
                    )
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
            
            time.sleep(interval)
    
    def get_live_metrics(self) -> Dict[str, Any]:
        """Получает актуальные метрики для API."""
        metrics = self.metrics_collector.get_system_metrics()
        alerts = self.alert_manager.check_alerts(metrics)
        dashboard_data = self.dashboard_data.get_dashboard_data()
        
        return {
            "status": "healthy" if not alerts else "warning",
            "metrics": asdict(metrics),
            "alerts": alerts,
            "dashboard": dashboard_data,
            "alert_history": list(self.alert_manager.alerts_history)[-10:]
        }
    
    def record_user_request(self) -> None:
        """Записывает пользовательский запрос."""
        self.metrics_collector.record_request()
    
    def record_error(self) -> None:
        """Записывает ошибку."""
        self.metrics_collector.record_error()
    
    def update_active_sessions(self, count: int) -> None:
        """Обновляет количество активных сессий."""
        # Обновляем счетчик в метриках
        if hasattr(self.metrics_collector, '_active_sessions'):
            self.metrics_collector._active_sessions = count
        else:
            self.metrics_collector._active_sessions = count
    
    def export_metrics(self, format_type: str = "json") -> str:
        """Экспортирует метрики в указанном формате."""
        data = self.get_live_metrics()
        
        if format_type == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif format_type == "prometheus":
            # Простой формат Prometheus
            metrics = data['metrics']
            lines = []
            lines.append(f"# HELP bot_cpu_usage CPU usage percentage")
            lines.append(f"# TYPE bot_cpu_usage gauge")
            lines.append(f"bot_cpu_usage {metrics['cpu_usage']}")
            lines.append(f"")
            lines.append(f"# HELP bot_memory_usage Memory usage percentage")
            lines.append(f"# TYPE bot_memory_usage gauge")
            lines.append(f"bot_memory_usage {metrics['memory_usage']}")
            lines.append(f"")
            lines.append(f"# HELP bot_requests_per_minute Requests per minute")
            lines.append(f"# TYPE bot_requests_per_minute gauge")
            lines.append(f"bot_requests_per_minute {metrics['requests_per_minute']}")
            lines.append(f"")
            lines.append(f"# HELP bot_error_rate Error rate percentage")
            lines.append(f"# TYPE bot_error_rate gauge")
            lines.append(f"bot_error_rate {metrics['error_rate']}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format_type}")


def main():
    """Основная функция мониторинга."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Мониторинг бота')
    parser.add_argument('--mode', choices=['report', 'live', 'daemon'], default='report',
                        help='Режим работы')
    parser.add_argument('--interval', type=int, default=30,
                        help='Интервал мониторинга в секундах')
    parser.add_argument('--export', choices=['json', 'prometheus'], 
                        help='Экспорт метрик')
    
    args = parser.parse_args()
    
    monitor = BotMonitor()
    
    if args.mode == 'report':
        # Генерируем и выводим отчет
        report = monitor.generate_report()
        print(report)
        
        # Сохраняем отчет в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"bot_status_report_{timestamp}.txt"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Отчет сохранен в файл: {report_file}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении отчета: {e}")
    
    elif args.mode == 'live':
        # Однократный вывод текущих метрик
        if args.export:
            print(monitor.export_metrics(args.export))
        else:
            metrics_data = monitor.get_live_metrics()
            print(json.dumps(metrics_data, indent=2, ensure_ascii=False))
    
    elif args.mode == 'daemon':
        # Запуск мониторинга в режиме демона
        print(f"📊 Запуск мониторинга в режиме демона...")
        print(f"Метрики будут собираться каждые {args.interval} секунд")
        print("Нажмите Ctrl+C для остановки")
        
        monitor.start_monitoring(args.interval)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nОстановка мониторинга...")
            monitor.stop_monitoring()


# Глобальный экземпляр монитора для использования в других модулях
_global_monitor: Optional[BotMonitor] = None


def get_monitor() -> BotMonitor:
    """Получает глобальный экземпляр монитора."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = BotMonitor()
    return _global_monitor


def init_monitoring(auto_start: bool = True, interval: int = 30) -> BotMonitor:
    """Инициализирует систему мониторинга."""
    monitor = get_monitor()
    if auto_start:
        monitor.start_monitoring(interval)
    return monitor


if __name__ == "__main__":
    main() 
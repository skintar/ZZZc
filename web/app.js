// TMA приложение для рейтинга персонажей
class CharacterRatingApp {
    constructor() {
        this.tg = window.Telegram.WebApp;
        this.currentScreen = 'loading';
        this.session = null;
        this.characters = [];
        this.currentPair = null;
        this.comparisonCount = 0;
        this.totalComparisons = 0;
        
        this.init();
    }

    async init() {
        // Настройка TMA
        this.tg.ready();
        this.tg.expand();
        this.tg.MainButton.hide();
        this.tg.BackButton.hide();

        // Обработчики событий
        this.setupEventListeners();
        
        // Загрузка данных
        await this.loadCharacters();
        await this.loadSession();
        
        this.showScreen('main-menu');
    }

    setupEventListeners() {
        // Главное меню
        document.getElementById('start-rating').addEventListener('click', () => this.startRating());
        document.getElementById('new-characters').addEventListener('click', () => this.startNewCharactersRating());
        document.getElementById('show-ranking').addEventListener('click', () => this.showRanking());
        document.getElementById('global-ranking').addEventListener('click', () => this.showGlobalRanking());

        // Сравнение
        document.querySelectorAll('.choose-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.makeChoice(e.target.dataset.choice));
        });
        document.getElementById('go-back').addEventListener('click', () => this.goBack());
        document.getElementById('skip-comparison').addEventListener('click', () => this.skipComparison());

        // Результаты
        document.getElementById('show-full-ranking').addEventListener('click', () => this.showFullRanking());
        document.getElementById('start-new-session').addEventListener('click', () => this.startRating());
        document.getElementById('back-to-menu').addEventListener('click', () => this.showScreen('main-menu'));
        document.getElementById('back-to-result').addEventListener('click', () => this.showScreen('ranking-result'));
        document.getElementById('back-to-menu-from-global').addEventListener('click', () => this.showScreen('main-menu'));

        // TMA кнопки
        this.tg.BackButton.onClick(() => this.handleBackButton());
    }

    async loadCharacters() {
        try {
            const response = await fetch('/api/characters');
            this.characters = await response.json();
        } catch (error) {
            console.error('Ошибка загрузки персонажей:', error);
            this.showError('Не удалось загрузить персонажей');
        }
    }

    async loadSession() {
        try {
            const response = await fetch('/api/session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: this.tg.initDataUnsafe.user?.id })
            });
            this.session = await response.json();
        } catch (error) {
            console.error('Ошибка загрузки сессии:', error);
        }
    }

    async startRating() {
        try {
            const response = await fetch('/api/start-rating', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    user_id: this.tg.initDataUnsafe.user?.id,
                    new_characters_only: false 
                })
            });
            
            if (response.ok) {
                this.session = await response.json();
                this.showComparison();
            } else {
                this.showError('Не удалось начать оценку');
            }
        } catch (error) {
            console.error('Ошибка начала оценки:', error);
            this.showError('Произошла ошибка');
        }
    }

    async startNewCharactersRating() {
        try {
            const response = await fetch('/api/start-rating', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    user_id: this.tg.initDataUnsafe.user?.id,
                    new_characters_only: true 
                })
            });
            
            if (response.ok) {
                this.session = await response.json();
                this.showComparison();
            } else {
                this.showError('Нет новых персонажей для оценки');
            }
        } catch (error) {
            console.error('Ошибка начала оценки новых персонажей:', error);
            this.showError('Произошла ошибка');
        }
    }

    showComparison() {
        this.currentPair = this.session.current_pair;
        if (!this.currentPair) {
            this.showRanking();
            return;
        }

        this.comparisonCount = this.session.comparisons_made || 0;
        this.totalComparisons = this.session.estimated_total || 0;

        this.updateProgress();
        this.displayCharacters();
        this.updateControls();
        this.showScreen('comparison');
    }

    displayCharacters() {
        const [a, b] = this.currentPair;
        const charA = this.characters.find(c => c.index === a);
        const charB = this.characters.find(c => c.index === b);

        if (!charA || !charB) {
            this.showError('Персонажи не найдены');
            return;
        }

        // Персонаж A
        document.getElementById('char-a-img').src = `/api/character-image/${a}`;
        document.getElementById('char-a-name').textContent = charA.name;

        // Персонаж B
        document.getElementById('char-b-img').src = `/api/character-image/${b}`;
        document.getElementById('char-b-name').textContent = charB.name;
    }

    updateProgress() {
        const progress = this.totalComparisons > 0 ? (this.comparisonCount / this.totalComparisons) * 100 : 0;
        document.getElementById('progress-fill').style.width = `${progress}%`;
        document.getElementById('progress-text').textContent = `${this.comparisonCount} / ${this.totalComparisons}`;
    }

    updateControls() {
        const goBackBtn = document.getElementById('go-back');
        if (this.session.choice_history && this.session.choice_history.length > 0) {
            goBackBtn.classList.remove('hidden');
        } else {
            goBackBtn.classList.add('hidden');
        }
    }

    async makeChoice(choice) {
        try {
            const response = await fetch('/api/make-choice', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.tg.initDataUnsafe.user?.id,
                    pair: this.currentPair,
                    choice: choice === 'a' ? this.currentPair[0] : this.currentPair[1]
                })
            });

            if (response.ok) {
                this.session = await response.json();
                this.showComparison();
            } else {
                this.showError('Не удалось сохранить выбор');
            }
        } catch (error) {
            console.error('Ошибка сохранения выбора:', error);
            this.showError('Произошла ошибка');
        }
    }

    async goBack() {
        try {
            const response = await fetch('/api/go-back', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.tg.initDataUnsafe.user?.id
                })
            });

            if (response.ok) {
                this.session = await response.json();
                this.showComparison();
            } else {
                this.showError('Не удалось отменить выбор');
            }
        } catch (error) {
            console.error('Ошибка отмены выбора:', error);
            this.showError('Произошла ошибка');
        }
    }

    async skipComparison() {
        // Пропуск сравнения - просто переходим к следующему
        this.showComparison();
    }

    async showRanking() {
        try {
            const response = await fetch('/api/ranking', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.tg.initDataUnsafe.user?.id
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.displayRanking(data.ranking, 'ranking-list');
                this.showScreen('ranking-result');
            } else {
                this.showError('Не удалось загрузить рейтинг');
            }
        } catch (error) {
            console.error('Ошибка загрузки рейтинга:', error);
            this.showError('Произошла ошибка');
        }
    }

    async showFullRanking() {
        try {
            const response = await fetch('/api/full-ranking', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.tg.initDataUnsafe.user?.id
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.displayRanking(data.ranking, 'full-ranking-list');
                this.showScreen('full-ranking');
            } else {
                this.showError('Не удалось загрузить полный рейтинг');
            }
        } catch (error) {
            console.error('Ошибка загрузки полного рейтинга:', error);
            this.showError('Произошла ошибка');
        }
    }

    async showGlobalRanking() {
        try {
            const response = await fetch('/api/global-ranking');
            const data = await response.json();
            this.displayRanking(data.ranking, 'global-ranking-list');
            this.showScreen('global-ranking-screen');
        } catch (error) {
            console.error('Ошибка загрузки глобального рейтинга:', error);
            this.showError('Произошла ошибка');
        }
    }

    displayRanking(ranking, containerId) {
        const container = document.getElementById(containerId);
        container.innerHTML = '';

        ranking.forEach((entry, index) => {
            const item = document.createElement('div');
            item.className = 'ranking-item';
            
            const position = document.createElement('div');
            position.className = `ranking-position ${index < 3 ? 'top-3' : ''}`;
            position.textContent = `#${index + 1}`;
            
            const character = document.createElement('div');
            character.className = 'ranking-character';
            character.textContent = entry.character_name;
            
            item.appendChild(position);
            item.appendChild(character);
            container.appendChild(item);
        });
    }

    showScreen(screenName) {
        // Скрываем все экраны
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.add('hidden');
        });

        // Показываем нужный экран
        document.getElementById(screenName).classList.remove('hidden');
        this.currentScreen = screenName;

        // Настройка кнопок TMA
        this.setupTMAButtons();
    }

    setupTMAButtons() {
        switch (this.currentScreen) {
            case 'comparison':
                this.tg.MainButton.setText('Пропустить');
                this.tg.MainButton.onClick(() => this.skipComparison());
                this.tg.MainButton.show();
                this.tg.BackButton.show();
                break;
            case 'ranking-result':
            case 'full-ranking':
            case 'global-ranking-screen':
                this.tg.MainButton.setText('Новая оценка');
                this.tg.MainButton.onClick(() => this.startRating());
                this.tg.MainButton.show();
                this.tg.BackButton.show();
                break;
            default:
                this.tg.MainButton.hide();
                this.tg.BackButton.hide();
        }
    }

    handleBackButton() {
        switch (this.currentScreen) {
            case 'comparison':
                this.showScreen('main-menu');
                break;
            case 'ranking-result':
                this.showScreen('main-menu');
                break;
            case 'full-ranking':
                this.showScreen('ranking-result');
                break;
            case 'global-ranking-screen':
                this.showScreen('main-menu');
                break;
            default:
                this.showScreen('main-menu');
        }
    }

    showError(message) {
        this.tg.showAlert(message);
    }
}

// Запуск приложения
document.addEventListener('DOMContentLoaded', () => {
    new CharacterRatingApp();
});

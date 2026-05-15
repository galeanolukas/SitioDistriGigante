// Enhanced Search Functionality
class EnhancedSearch {
  constructor() {
    this.searchInput = null;
    this.searchSuggestions = null;
    this.searchResults = null;
    this.loadingIndicator = null;
    this.noResults = null;
    this.debounceTimer = null;
    this.minSearchLength = 2;
    this.currentQuery = '';
    
    this.init();
  }

  init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.setupSearch());
    } else {
      this.setupSearch();
    }
  }

  setupSearch() {
    // Find search elements
    this.searchInput = document.querySelector('.enhanced-search-input');
    this.searchSuggestions = document.querySelector('.search-suggestions');
    this.searchResults = document.querySelector('.search-results');
    this.loadingIndicator = document.querySelector('.search-loading');
    this.noResults = document.querySelector('.search-no-results');

    if (this.searchInput) {
      this.attachEventListeners();
      this.setupKeyboardNavigation();
    }
  }

  attachEventListeners() {
    // Input event with debouncing
    this.searchInput.addEventListener('input', (e) => {
      const query = e.target.value.trim();
      this.handleSearchInput(query);
    });

    // Focus events
    this.searchInput.addEventListener('focus', () => {
      if (this.searchInput.value.trim().length >= this.minSearchLength) {
        this.showSuggestions();
      }
    });

    // Click outside to close
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.search-container')) {
        this.hideSuggestions();
      }
    });

    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(chip => {
      chip.addEventListener('click', (e) => {
        this.toggleFilter(e.target);
        this.performSearch();
      });
    });
  }

  setupKeyboardNavigation() {
    this.searchInput.addEventListener('keydown', (e) => {
      const items = this.searchSuggestions.querySelectorAll('.suggestion-item');
      let currentIndex = -1;

      // Find current selected item
      items.forEach((item, index) => {
        if (item.classList.contains('selected')) {
          currentIndex = index;
        }
      });

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          if (currentIndex < items.length - 1) {
            if (currentIndex >= 0) items[currentIndex].classList.remove('selected');
            items[currentIndex + 1].classList.add('selected');
          }
          break;

        case 'ArrowUp':
          e.preventDefault();
          if (currentIndex > 0) {
            items[currentIndex].classList.remove('selected');
            items[currentIndex - 1].classList.add('selected');
          }
          break;

        case 'Enter':
          e.preventDefault();
          if (currentIndex >= 0) {
            items[currentIndex].click();
          } else {
            this.performSearch();
          }
          break;

        case 'Escape':
          this.hideSuggestions();
          this.searchInput.blur();
          break;
      }
    });
  }

  handleSearchInput(query) {
    // Clear previous timer
    clearTimeout(this.debounceTimer);

    if (query.length < this.minSearchLength) {
      this.hideSuggestions();
      return;
    }

    // Set new timer for debounced search
    this.debounceTimer = setTimeout(() => {
      this.performSearch(query);
    }, 300);
  }

  async performSearch(query = null) {
    const searchQuery = query || this.searchInput.value.trim();
    
    if (!searchQuery || searchQuery.length < this.minSearchLength) {
      this.hideSuggestions();
      return;
    }

    this.currentQuery = searchQuery;
    this.showLoading();

    try {
      // Simulate API call - replace with actual endpoint
      const results = await this.fetchSearchResults(searchQuery);
      this.displayResults(results);
    } catch (error) {
      console.error('Search error:', error);
      this.showError();
    } finally {
      this.hideLoading();
    }
  }

  async fetchSearchResults(query) {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // Mock data - replace with actual API call
    const mockProducts = [
      {
        id: 1,
        name: 'Producto Ejemplo 1',
        category: 'Electrónica',
        price: 19999,
        image: '/static/img/product1.jpg'
      },
      {
        id: 2,
        name: 'Producto Ejemplo 2',
        category: 'Hogar',
        price: 8999,
        image: '/static/img/product2.jpg'
      }
    ];

    // Filter mock results based on query
    return mockProducts.filter(product => 
      product.name.toLowerCase().includes(query.toLowerCase()) ||
      product.category.toLowerCase().includes(query.toLowerCase())
    );
  }

  displayResults(results) {
    if (!this.searchSuggestions) return;

    this.searchSuggestions.innerHTML = '';

    if (results.length === 0) {
      this.showNoResults();
      return;
    }

    results.forEach((result, index) => {
      const suggestionItem = this.createSuggestionItem(result, index);
      this.searchSuggestions.appendChild(suggestionItem);
    });

    this.showSuggestions();
  }

  createSuggestionItem(result, index) {
    const item = document.createElement('div');
    item.className = 'suggestion-item';
    item.setAttribute('data-index', index);
    
    item.innerHTML = `
      <div class="suggestion-icon">
        <i class="fas fa-box"></i>
      </div>
      <div class="suggestion-content">
        <div class="suggestion-title">${this.highlightMatch(result.name)}</div>
        <div class="suggestion-category">${result.category}</div>
      </div>
      <div class="suggestion-price">$${result.price.toLocaleString()}</div>
    `;

    item.addEventListener('click', () => {
      this.selectSuggestion(result);
    });

    return item;
  }

  highlightMatch(text) {
    if (!this.currentQuery) return text;
    
    const regex = new RegExp(`(${this.currentQuery})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
  }

  selectSuggestion(result) {
    // Navigate to product detail or add to cart
    window.location.href = `/producto/${result.id}`;
  }

  toggleFilter(chip) {
    chip.classList.toggle('active');
  }

  getActiveFilters() {
    const activeFilters = [];
    document.querySelectorAll('.filter-chip.active').forEach(chip => {
      activeFilters.push(chip.dataset.filter);
    });
    return activeFilters;
  }

  showSuggestions() {
    if (this.searchSuggestions) {
      this.searchSuggestions.classList.add('active');
    }
  }

  hideSuggestions() {
    if (this.searchSuggestions) {
      this.searchSuggestions.classList.remove('active');
    }
  }

  showLoading() {
    if (this.loadingIndicator) {
      this.loadingIndicator.classList.add('active');
    }
  }

  hideLoading() {
    if (this.loadingIndicator) {
      this.loadingIndicator.classList.remove('active');
    }
  }

  showNoResults() {
    if (this.noResults) {
      this.noResults.classList.add('active');
    }
    this.hideSuggestions();
  }

  hideNoResults() {
    if (this.noResults) {
      this.noResults.classList.remove('active');
    }
  }

  showError() {
    const errorHtml = `
      <div class="search-error">
        <i class="fas fa-exclamation-triangle"></i>
        <p>Error al buscar productos. Por favor, intenta nuevamente.</p>
      </div>
    `;
    
    if (this.searchSuggestions) {
      this.searchSuggestions.innerHTML = errorHtml;
      this.showSuggestions();
    }
  }
}

// Auto-initialize when script loads
const enhancedSearch = new EnhancedSearch();

// Export for potential external use
window.EnhancedSearch = EnhancedSearch;

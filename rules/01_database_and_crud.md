# BAZA DANYCH, OPERACJE CRUD I WALIDACJA

1. **Ochrona Bazowych Miejsc (Base=true):**
   - Miejsca z flagą `Base=true` są bezwzględnie chronione. Zabrania się ich usuwania i modyfikacji kluczowych parametrów bazowych. Dozwolone jest tylko dodawanie nowych miejsc, notatek i modyfikacja dynamicznych wycieczek/kroków.

2. **Zasada Unikania "Użytych" Miejsc oraz Wyjątki:**
   - **Co do zasady unikaj ponownego proponowania miejsc oznaczonych jako odwiedzone (`odwiedzone = 1`)** w nowych wycieczkach. 
   - **Wyjątek:** Jeśli użytkownik wyraźnie się upiera lub zaznaczy, że część ekipy jeszcze tam nie była, asystent ma w pełni pozwolić na dodanie takiego miejsca do planu.

3. **Zasada Bezwzględnego Sprawdzania ID i Zapobieganie Błędom Constraint:**
   - **NIGDY nie zgaduj ID kroków (`id_kroku`) ani ID wycieczek.** Zawsze najpierw przeanalizuj kontekst bazy danych, odnajdź dokładne `DB_ID`, a dopiero potem wywołuj funkcje (np. dodawanie zakupów do konkretnego kroku).
   - Przed wywołaniem jakiejkolwiek funkcji zapisu weryfikuj kompletność wymaganych pól, aby uniknąć błędów naruszenia ograniczeń bazy danych (SQLite constraint violation). W razie braku danych – dopytaj użytkownika.

4. **Formatowanie Danych:**
   - Daty zawsze w formacie `RRRR-MM-DD`, współrzędne jako ciąg `"szerokość, długość"`.

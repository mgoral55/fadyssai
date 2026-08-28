# WORKFLOW WYCIECZEK, POSIŁKI I LOGISTYKA

1. **Poranna Logistyka i Czas do Wyjścia (Standard 1.5h):**
   - Standardowo rodzina potrzebuje średnio **1,5 godziny od pobudki do wyjścia z domu** (przygotowanie, leki, pakowanie, ubranie dzieci z ADHD bez pośpiechu).
   - Planując wycieczki, asystent musi uwzględniać ten bufor czasowy (np. pobudka o 07:00 oznacza wyjazd najwcześniej o 08:30). 
   - Jeśli harmonogram wymaga wcześniejszego wyjazdu (np. biletowany wstęp na otwarcie o 08:00 w Knossos), asystent ma obowiązek zaproponować **śniadanie w aucie** lub spakowanie prostych przekąsek na drogę, aby nie generować porannego stresu.

2. **Dynamiczne Przeliczanie Czasu przy Modyfikacji Kroków:**
   - Kiedy użytkownik modyfikuje plan, dodaje nowy krok (np. poranny sklep lub dodatkową atrakcję) lub zmienia kolejność, asystent ma bezwzględny obowiązek **przeliczyć harmonogram godzinowy dla wszystkich kolejnych kroków**.
   - Jeśli dodanie punktu wciśniętego na rano lub w ciągu dnia powoduje kaskadowe opóźnienie lub brak wymaganego bufora, asystent musi sprawdzić, czy konieczne jest wcześniejsze wstanie i poinformować o tym użytkownika wprost (np.: *"Dodanie sklepu rano o 08:00 oznacza, że musimy przesunąć pobudkę na 06:30 albo opóźnić Knossos o 30 minut. Czy zatwierdzasz tę zmianę?"*), czekając na akceptację przed zapisaniem zmian w bazie.

3. **Weryfikacja Posiłków (Obiad i Kolacja):**
   - Zawsze sprawdzaj harmonogram pod kątem obiadu (około południa) i kolacji. Jeśli ich brak, zapytaj: *"Zauważyłem brak obiadu. Doradzić coś czy zjecie w domku?"*
   - **Brak restauracji jako oddzielnych miejsc w bazie:** Restauracje co do zasady nie są dodane w liście miejsc jako osobne obiekty w bazie danych. Jeśli w planie nie ma uwzględnionego obiadu i nie ma opcji powrotu do domku w porze obiadowej, asystent **nie ma szukać restauracji na siłę w tabeli miejsc z DB**, lecz napisać ogólnie: *"restauracja w pobliżu [nazwa miejsca]"*.

4. **Logika Posiłków w Domku, Sklepów i Składników:**
   - **Obowiązkowe pytanie o składniki:** Jeśli w planie wycieczki dodajemy lub mamy zaplanowany obiad i/lub kolację w domku, asystent ma obowiązek zawsze dopytać rodzica: *"Czy na pewno macie wszystkie potrzebne składniki w domku, czy nie trzeba uwzględnić sklepu w planie?"*
   - **Dodawanie kroku sklepowego:** Jeśli użytkownik potwierdzi brak składników lub potrzebę wizyty w sklepie, wpnij sklep jako krok na trasie (`dodaj_krok_wycieczki`) oraz uzupełnij checklistę brakujących produktów (`dodaj_produkt_zakupow`).

5. **Protokół Powrotu do Domku i Głodnych Dzieci (16:00 / Okno 2h):**
   - Jeśli między ostatnim posiłkiem (np. obiadem o 12:00) a powrotem do domku (np. o 16:00) mija więcej niż 2,5 godziny, asystent musi bezwzględnie umieścić w taktyce powrotnej **Ostrzeżenie o Głodzie Popołudniowym**.
   - **Awaryjna zupa / Szybki posiłek:** Przypomnienie: *"Dzieci będą bardzo głodne po drodze! Upewnij się, że w domku czeka ekspresowy posiłek (np. gotowa zupa, parówki) lub miej w aucie bułki/musy, by zaspokoić wilczy głód w 5 minut po przyjeździe, zanim ruszy gotowanie."*

6. **Zmiana Kolejności i Targ w Chani:**
   - Przy zmianie kolejności lub wstawianiu kroków analizuj aktualne ID i godziny, by harmonogram był spójny.
   - Gdy w planie pojawia się "targ w Chani" z datą, sprawdź dzień tygodnia, przeanalizuj załączone pliki PDF w źródłach, znajdź właściwy adres/współrzędne dla danego dnia i zaktualizuj krok.

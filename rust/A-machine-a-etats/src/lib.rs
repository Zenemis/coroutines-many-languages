//! Variante A : coroutines sous forme de machines à états écrites à la main.
//!
//! Sémantique : celle de `std::ops::Coroutine` (voir ../README.md).

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CoroutineState<Y, R> {
    Yield(Y),
    Return(R),
}

pub fn cr_yield<Y, R>(mut f: impl FnMut() -> Y + 'static) -> 
    Box<dyn FnMut() -> CoroutineState<Y, R>> {
        Box::new(move || CoroutineState::Yield(f()))
}

pub fn cr_return<Y, R>(mut f: impl FnMut() -> R + 'static) -> 
    Box<dyn FnMut() -> CoroutineState<Y, R>> {
        Box::new(move || CoroutineState::Return(f()))
}

pub struct Coroutine<Y, R> {
    state: Option<usize>,
    bodies: Vec<Box<dyn FnMut() -> CoroutineState<Y, R>>>,
}

impl<Y, R> Coroutine<Y, R> {
    pub fn new(sequence: Vec<Box<dyn FnMut() -> CoroutineState<Y, R>>>) -> Self {
        Coroutine { 
            state: Some(0), 
            bodies: sequence
        }
    }

    pub fn resume(&mut self) -> CoroutineState<Y, R> {
        let i = self.state.unwrap();
        let val = self.bodies[i]();
        match val {
            CoroutineState::Yield(_) => {
                self.state = Some(i + 1);
            },
            CoroutineState::Return(_) => {
                self.state = None;
            },
        }
        val
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::RefCell;
    use std::panic::{AssertUnwindSafe, catch_unwind};
    use std::rc::Rc;

    use CoroutineState::{Return, Yield};

    /// Un journal partagé : les morceaux y notent ce qu'ils exécutent, ce qui
    /// permet de vérifier QUAND le code de la coroutine tourne.
    /// (Les morceaux sont `'static` : ils ne peuvent pas emprunter une variable
    /// du test, d'où le `Rc<RefCell<…>>` cloné dans chaque closure.)
    type Journal = Rc<RefCell<Vec<&'static str>>>;

    fn cuisinier(journal: &Journal) -> Coroutine<(), ()> {
        let (j1, j2, j3) = (journal.clone(), journal.clone(), journal.clone());
        Coroutine::new(vec![
            cr_yield(move || j1.borrow_mut().push("je coupe les légumes")),
            cr_yield(move || j2.borrow_mut().push("je fais cuire")),
            cr_return(move || j3.borrow_mut().push("le plat est prêt")),
        ])
    }

    #[test]
    fn produit_les_valeurs_dans_l_ordre_puis_termine() {
        let mut c: Coroutine<&'static str, &'static str> = Coroutine::new(vec![
            cr_yield(|| "vert"),
            cr_yield(|| "orange"),
            cr_return(|| "eteint"),
        ]);
        assert_eq!(c.resume(), Yield("vert"));
        assert_eq!(c.resume(), Yield("orange"));
        assert_eq!(c.resume(), Return("eteint"));
    }

    #[test]
    fn la_creation_n_execute_rien() {
        let journal = Journal::default();
        let _c = cuisinier(&journal);
        assert!(journal.borrow().is_empty(), "la création a exécuté : {:?}", journal.borrow());
    }

    #[test]
    fn chaque_reprise_execute_exactement_un_morceau() {
        let journal = Journal::default();
        let mut c = cuisinier(&journal);

        assert_eq!(c.resume(), Yield(()));
        assert_eq!(*journal.borrow(), ["je coupe les légumes"]);

        assert_eq!(c.resume(), Yield(()));
        assert_eq!(*journal.borrow(), ["je coupe les légumes", "je fais cuire"]);

        assert_eq!(c.resume(), Return(()));
        assert_eq!(*journal.borrow(), ["je coupe les légumes", "je fais cuire", "le plat est prêt"]);
    }

    #[test]
    fn peut_terminer_sans_jamais_se_suspendre() {
        let mut c: Coroutine<i32, &'static str> = Coroutine::new(vec![cr_return(|| "fini")]);
        assert_eq!(c.resume(), Return("fini"));
    }

    #[test]
    #[should_panic]
    fn reprendre_apres_la_fin_panique() {
        let mut c: Coroutine<(), ()> = Coroutine::new(vec![cr_return(|| ())]);
        c.resume();
        c.resume();
    }

    #[test]
    fn reprendre_apres_la_fin_panique_a_chaque_fois_sans_rejouer_de_code() {
        let journal = Journal::default();
        let mut c = cuisinier(&journal);
        for _ in 0..3 {
            c.resume();
        }
        for tentative in 1..=2 {
            let r = catch_unwind(AssertUnwindSafe(|| c.resume()));
            assert!(r.is_err(), "la reprise n°{tentative} après la fin n'a pas paniqué");
        }
        assert_eq!(journal.borrow().len(), 3, "du code a été rejoué : {:?}", journal.borrow());
    }

    #[test]
    fn deux_instances_sont_independantes() {
        let journal = Journal::default();
        let mut a = cuisinier(&journal);
        let mut b = cuisinier(&journal);

        assert_eq!(a.resume(), Yield(()));
        assert_eq!(a.resume(), Yield(()));
        assert_eq!(b.resume(), Yield(()));
        assert_eq!(a.resume(), Return(()));
        assert_eq!(b.resume(), Yield(()));
        assert_eq!(b.resume(), Return(()));

        assert_eq!(
            *journal.borrow(),
            [
                "je coupe les légumes", // a
                "je fais cuire",        // a
                "je coupe les légumes", // b
                "le plat est prêt",     // a
                "je fais cuire",        // b
                "le plat est prêt",     // b
            ]
        );
    }

    #[test]
    fn peut_produire_des_valeurs_non_copy() {
        // Vérifie que le problème du `derive(Copy)` est bien réglé :
        // `String` n'est pas `Copy`, et chaque reprise rend une valeur neuve.
        let mut c: Coroutine<String, Vec<String>> = Coroutine::new(vec![
            cr_yield(|| String::from("bonjour")),
            cr_return(|| vec![String::from("au"), String::from("revoir")]),
        ]);
        assert_eq!(c.resume(), Yield(String::from("bonjour")));
        assert_eq!(c.resume(), Return(vec![String::from("au"), String::from("revoir")]));
    }
}

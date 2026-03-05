export interface Location {
  id: number;
  name: string;
  is_correct: boolean;
}

export interface Round {
  id: number;
  original_url: string;
  ai_url: string;
  solution_text: string;
  target_year: number;
  time_limit: number;
  position: number;
  locations: Location[];
}

export interface Game {
  uuid: string;
  title: string;
  status: 'lobby' | 'active' | 'finished';
  join_url: string;
  created_at: string;
  rounds: Round[];
  participants: Participant[];
}

export interface Participant {
  id: number;
  username: string;
  score: number;
  ready: boolean;
  locked: boolean;
}

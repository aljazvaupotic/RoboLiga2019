//izziv3.java
// Aljaz Vaupotic	

import java.util.*


public class izziv3 {

	public static void main(String[] args) {
		int n, m;
		Scanner sc = new Scanner(System.in);
		n = sc.nextInt();
		m = sc.nextInt();
		int len = n+m;
		int[] first = new int[n];
		int[] second = new int[m];
		int[] order = new int [len];
		
		for(int i = 0; i < n; i++){
			first[i] = sc.nextInt();
		}
		for(int j = 0; j < m; j++){
			second[j] = sc.nextInt();
		}

		int urejeni = 0;
		int neurejeni = len;
		int f = 0;
		int s = 0;

		while(urejeni != neurejeni){
			if(first[f] <= second[s]){
				order[urejeni] = first[f];
				f++;
				urejeni++;
				System.out.print("a"); 
			}else {
				order[urejeni] = second[s];
				s++;
				urejeni++;
				System.out.print("b");
			}
		}
		for (int m = 0 ; m < len ; m++ ) {
			System.out.print(order[m] + " ");
		}

		
	}
}


